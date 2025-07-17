#!/usr/bin/env python
import sys
import os
import subprocess
import readline
import json
import glob

from litellm import completion
from typing import List, Literal, TextIO, Tuple, Dict, Type, Optional, Final

FileMode = Literal["w", "a"]


class CommandError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return self.message


class UserInput:
    def __init__(
        self,
        input_parts: List[str],
        output_file: Optional[Tuple[str, FileMode]] = None,
        error_file: Optional[Tuple[str, FileMode]] = None,
    ):
        self.input_parts = input_parts
        self.output_file = output_file
        self.error_file = error_file

    def __repr__(self) -> str:
        return (
            f"UserInput(input_parts={self.input_parts}, "
            f"output_file={self.output_file}, error_file={self.error_file})"
        )

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, UserInput)
            and self.input_parts == value.input_parts
            and self.output_file == value.output_file
            and self.error_file == value.error_file
        )


class Command:
    def __init__(self, name: str):
        self.name = name
        self.out_stream = sys.stdout
        self.err_stream = sys.stderr
        self.in_stream = sys.stdin

    def execute(self, args: List[str]):
        pass

    def tear_down(self):
        if self.out_stream and self.out_stream != sys.stdout:
            self.out_stream.close()
            self.out_stream = sys.stdout

        if self.err_stream and self.err_stream != sys.stderr:
            self.err_stream.close()
            self.err_stream = sys.stderr

        if self.in_stream and self.in_stream != sys.stdin:
            self.in_stream.close()
            self.in_stream = sys.stdin

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


class PipelineCommand(Command):
    def __init__(self, commands: List[Tuple[Command, List[str]]]):
        super().__init__(f"pipeline: {commands}")
        self.commands = commands

    def execute(self, args: List[str]):
        previous_pipe = None
        pids = []
        for i, (cmd, cmd_params) in enumerate(self.commands):
            current_pipe = None

            # Check if we need to create a pipe for the next command
            if i < len(self.commands) - 1:
                current_pipe = os.pipe()

            cmd_pid = os.fork()
            if cmd_pid == 0:
                # Child process
                # The pipe is a tuple (read_fd, write_fd)

                if current_pipe:
                    # If there is a current pipe, there is a next command, we only need the write end
                    os.close(current_pipe[0])
                    cmd.out_stream = os.fdopen(current_pipe[1], "w")

                if previous_pipe:
                    # We only need the read end of the previous pipe (if any)
                    os.close(previous_pipe[1])
                    cmd.in_stream = os.fdopen(previous_pipe[0], "r")

                cmd.execute(cmd_params)
                cmd.tear_down()

                os._exit(0)
                return

            # Parent process
            if previous_pipe:
                os.close(previous_pipe[0])
                os.close(previous_pipe[1])

            previous_pipe = current_pipe
            pids.append(cmd_pid)

        if previous_pipe:
            raise CommandError("There is a previous pipe that was not closed")

        for cmd_pid in pids:
            # Wait for the child processes to finish
            # We need to wait for all the child processes to avoid zombie processes
            # TODO handle the exit status of the child processes
            os.waitpid(cmd_pid, 0)

    def tear_down(self):
        super().tear_down()
        for command, _ in self.commands:
            command.tear_down()


class CommandNotFound(Command):
    def __init__(self, name: str):
        super().__init__(name)

    def execute(self, args: List[str]):
        print(f"{self.name}: Command not found", file=self.err_stream)


class ExecutableCommand(Command):
    def __init__(self, command_path: str):
        super().__init__(os.path.basename(command_path))
        self.command_path = command_path

    def execute(self, args: List[str]):
        cmd = [self.name]
        cmd.extend(args)
        subprocess.run(
            cmd, stdout=self.out_stream, stderr=self.err_stream, stdin=self.in_stream
        )


class AssignmentCommand(Command):
    def __init__(self, var_name: str, val: str):
        super().__init__("")
        self.var_name = var_name
        self.val = val

    def execute(self, args: List[str]):
        os.environ[self.var_name] = self.val


class BuiltinCommand(Command):
    def __init__(self, name: str):
        super().__init__(name)


class EchoCommand(BuiltinCommand):
    NAME = "echo"

    def __init__(self):
        super().__init__(EchoCommand.NAME)

    def execute(self, args: List[str]):
        # TODO handle flag aruments
        print(" ".join(args), file=self.out_stream)


class ExitCommand(BuiltinCommand):
    NAME = "exit"

    def __init__(self, shell: "PyShell"):
        super().__init__(ExitCommand.NAME)
        self.shell = shell

    def execute(self, args: List[str]):
        exit_code = 0
        if args:
            try:
                exit_code = int(args[0])
            except ValueError:
                raise CommandError(f"{args[0]}: numeric argument required")

        self.shell.exit(exit_code)


class TypeCommand(BuiltinCommand):
    NAME = "type"

    def __init__(self, shell: "PyShell"):
        super().__init__(TypeCommand.NAME)
        self.shell = shell

    def execute(self, args: List[str]):
        if not args:
            return

        for arg in args:
            command_factory = self.shell._find_command(arg)
            if issubclass(command_factory.command_type, AICommand):
                print(f"{arg} is an AI builtin", file=self.out_stream)
            elif issubclass(command_factory.command_type, BuiltinCommand):
                print(f"{arg} is a shell builtin", file=self.out_stream)
            elif issubclass(command_factory.command_type, ExecutableCommand):
                # For executable commands, the first argument of the factory is the command path
                print(f"{arg} is {command_factory.args[0]}", file=self.out_stream)
            else:
                print(f"{arg}: not found", file=self.err_stream)


class PwdCommand(BuiltinCommand):
    NAME = "pwd"

    def __init__(self):
        super().__init__(PwdCommand.NAME)

    def execute(self, args: List[str]):
        print(os.getcwd(), file=self.out_stream)


class CdCommand(BuiltinCommand):
    NAME = "cd"

    def __init__(self, shell: "PyShell"):
        super().__init__(CdCommand.NAME)
        self.shell = shell

    def execute(self, args: List[str]):
        if not args:
            args = ["~"]

        if len(args) > 1:
            raise CommandError(f"too many arguments")

        # Use expanduser to handle special cases like '~'
        target_dir = os.path.expanduser(args[0])

        if target_dir == "-":
            if self.shell._last_dir:
                target_dir = self.shell._last_dir
        elif not os.path.exists(target_dir):
            raise CommandError(f"{target_dir}: No such file or directory")
        elif not os.path.isdir(target_dir):
            raise CommandError(f"{target_dir}: Not a directory")

        self.shell._last_dir = os.getcwd()
        os.chdir(target_dir)


class HistoryCommand(BuiltinCommand):
    NAME = "history"

    def __init__(self, shell: "PyShell"):
        super().__init__(HistoryCommand.NAME)
        self.shell = shell

    def execute(self, args: List[str]):
        history_start = 0
        history_end = readline.get_current_history_length() + 1
        supported_flags = ["-r", "-w", "-a"]

        if args:
            if args[0] in supported_flags:
                if len(args) == 1:
                    raise CommandError(f"{args[0]}: file name required")

                if len(args) > 2:
                    raise CommandError(f"too many arguments")

                flag = args[0]
                filename = args[1]

                if flag == "-r":
                    readline.read_history_file(filename)
                    return

                if flag == "-w":
                    readline.write_history_file(filename)
                    return

                if flag == "-a":
                    nelements = (
                        readline.get_current_history_length()
                        - self.shell.last_apended_history_item
                    )
                    readline.append_history_file(nelements, filename)
                    self.shell.last_apended_history_item = (
                        readline.get_current_history_length()
                    )
                    return
            elif args[0].startswith("-"):
                raise CommandError(f"{args[0]}: unknown argument")

            if len(args) > 1:
                raise CommandError(f"too many arguments")

            try:
                history_start = max(0, history_end - int(args[0]))
            except ValueError:
                raise CommandError(f"{args[0]}: numeric argument required")

        for i in range(history_start, history_end):
            history_item = readline.get_history_item(i)
            print(f"\t{i}  {history_item}", file=self.out_stream)


class AICommand(BuiltinCommand):
    def __init__(self, name: str, shell: "PyShell"):
        super().__init__(name)
        self.memory = []
        self.shell = shell

    def add_to_memory(self, message: Dict):
        self.memory.append(message)

    def get_response_from_ai(self) -> str:
        shell_config = self.shell.config
        ai_config = shell_config.get("ai_config")
        if not ai_config:
            raise CommandError(
                f"AI configuration not found in {PyShell.PYSHELL_CONFIG_FILE}"
            )

        provider = ai_config.get("provider")
        model = ai_config.get("model")
        token = ai_config.get("token")

        result = ""
        try:
            response = completion(
                model=f"{provider}/{model}",
                messages=self.memory,
                api_key=token,
                max_tokens=1024,
            )
            result = response.choices[0].message.content or ""
        except Exception as e:
            result = ""

        return result

    def _configure_ai(self) -> bool:
        print(
            "Before using an AI builtin, there's a few parameters you need to configure:"
        )
        provider = input("Enter AI provider (e.g., openai): ").strip()
        model = input("Enter AI model (e.g., gpt-4o-mini): ").strip()
        token = input("Enter AI token: ").strip()

        if not provider or not model or not token:
            return False

        self.shell.update_config(
            "ai_config", {"provider": provider, "model": model, "token": token}
        )
        return True

    def execute_ai(self, args: List[str]):
        pass

    def execute(self, args: List[str]):
        # Make sure we have all configs we need to run the LLM query
        shell_config = self.shell.config
        if not shell_config.get("ai_config"):
            # Prompt the user to configure the parameters needed to access the AI
            if not self._configure_ai():
                raise CommandError(
                    "AI configuration failed. Please configure it properly before using AI built-ins."
                )

        self.execute_ai(args)


class DoCommand(AICommand):
    NAME = "do"

    SYSTEM_PROMPT = """
    You are a highly experienced Unix system administrator and command line expert. Given a natural 
    language task, output a Bash command that solves it, along with a safety assessment and explanation.

    Your response must contain the following information:
    1. A bash command that solves the problem. If the problem can't be solved, return an empty string 
       for the command 
    2. A risk assessment of the command, as follows:
        - Risk 0: Safe to run. No data is modified or deleted.
        - Risk 1: May modify or delete user data, but not system-critical files.
        - Risk 2: May impact system integrity, security, or availability (e.g., running as root, 
          altering system files).
        - If the command is empty, the risk assessment must also be 0.
    3. An explanation of the command and how it achieves the solution.
    4. A disclaimer message shown to the user if the command carries any risk (i.e., risk > 0). This
    message must warn the user about what could happen if the command is executed. If the command is
    safe (risk 0), return an empty string.

    Make sure your response is a valid JSON object in the following format (with double quotes and no 
    trailing commas):
    {
        "command": "<bash command>",
        "risk_assessment": <0|1|2>,
        "explanation": "<explanation of the command>",
        "disclaimer": "<disclaimer shown if risk > 0, empty string otherwise>"
    }

    Ensure the JSON is valid and can be parsed with standard JSON parsers. 
    Do not include markdown, code blocks, or comments. Only output the JSON.
    """

    def __init__(self, shell: "PyShell"):
        super().__init__(DoCommand.NAME, shell)
        self.sub_command = None

        # Init the memory with the system prompt
        self.add_to_memory({"role": "system", "content": DoCommand.SYSTEM_PROMPT})

    # Override here to ensure we get a valid response from the AI. Otherwise fail with a CommandError
    def get_structured_response_from_ai(self) -> Dict:
        raw_response = super().get_response_from_ai()

        try:
            response = json.loads(raw_response)
        except Exception:
            response = None

        if not response:
            raise CommandError("Failed to get a valid response from the AI")

        if (
            "command" not in response
            or "risk_assessment" not in response
            or "explanation" not in response
            or "disclaimer" not in response
        ):
            raise CommandError("Invalid response format from the AI")

        return response

    def _show_warning_message(self, message: str) -> bool:
        print(f"WARNING!\n-------------------------------")
        print(message)
        print(
            "-------------------------------\nAre you sure you want to continue? (y/n)"
        )
        confirmation = input().strip().lower()
        if confirmation != "y":
            return False
        return True

    def execute_ai(self, args: List[str]):
        user_prompt = " ".join(args)
        if not user_prompt:
            print(f"No command provided to '{DoCommand.NAME}'", file=self.err_stream)
            return

        self.add_to_memory({"role": "user", "content": user_prompt})
        response = self.get_structured_response_from_ai()

        if not response["command"]:
            print(response["explanation"], file=self.err_stream)
            return
        
        self.shell.show_intenral_message(f"Executing '{response['command']}'...")

        if response["risk_assessment"] > 0:
            if not self._show_warning_message(response["disclaimer"]):
                return

        command, args = self.shell._eval(response["command"])
        command.out_stream = self.out_stream
        command.err_stream = self.err_stream

        self.sub_command = command
        self.sub_command.execute(args)

    def tear_down(self):
        if self.sub_command:
            self.sub_command.tear_down()

        return super().tear_down()


class ExplainCommand(AICommand):
    NAME = "explain"

    SYSTEM_PROMPT = """
    You are a highly experienced Unix system administrator and command line expert. Given a Bash command, 
    output a detailed explanation of what the command does, including its components and their roles.
    Also provide one or 2 examples on how to use that command in a real-world scenario.
    If the input provided is a complex command (e.g., a pipeline), break it down into its components
    and explain each part.

    Make sure to keep your answer short and concise, focusing on the key aspects of the command.
    Make it at most 5 lines long, and use simple language that is easy to understand.
    Do not include markdown, code blocks, or comments. Only output the explanation.
    """

    def __init__(self, shell: "PyShell"):
        super().__init__(ExplainCommand.NAME, shell)

        # Init the memory with the system prompt
        self.add_to_memory({"role": "system", "content": ExplainCommand.SYSTEM_PROMPT})

    def execute_ai(self, args: List[str]):
        user_prompt = " ".join(args)
        if not user_prompt:
            return

        self.add_to_memory({"role": "user", "content": user_prompt})
        response = self.get_response_from_ai()
        print(response, file=self.out_stream)


class CommandFactory:
    def __init__(self, command_type: Type[Command], *args, **kwargs):
        self.command_type = command_type
        self.args = args
        self.kwargs = kwargs

    def make(
        self,
        out_stream: Optional[TextIO] = None,
        err_stream: Optional[TextIO] = None,
        in_stream: Optional[TextIO] = None,
    ) -> Command:
        cmd = self.command_type(*self.args, **self.kwargs)
        if out_stream is not None:
            cmd.out_stream = out_stream

        if err_stream is not None:
            cmd.err_stream = err_stream

        if in_stream is not None:
            cmd.in_stream = in_stream

        return cmd


class InputParser:
    def __init__(self, user_input: str):
        self.states: Final = {
            "default": self._default_state_handler,
            "single_quote": self._single_quote_state_handler,
            "double_quote": self._double_quote_state_handler,
            "inter_redirect": self._intermediary_redirect_state_handler,
            "append_redirect": self._append_redirect_state_handler,
            "error_redirect": self._error_redirect_state_handler,
            "out_redirect": self._out_redirect_state_handler,
            "env_variable": self._env_variable_state_handler,
        }

        self.user_input = user_input
        self.state_stack = ["default"]

        self.env_variable = ""
        self.current_part = ""
        self.current_parts: List[str] = []
        self.current_out_file: Optional[Tuple[str, FileMode]] = None
        self.current_err_file: Optional[Tuple[str, FileMode]] = None

        # The pipeline of user inputs, each input is a UserInput object
        # This will be filled with UserInput objects as the input is parsed
        self.pipeline: List[UserInput] = []

    def parse(self) -> List[UserInput]:
        is_escaped = False

        if not self.user_input.strip():
            # If the input is empty or only contains whitespace, return an empty UserInput
            return [UserInput([])]

        for i, c in enumerate(self.user_input):
            is_escaped = i > 0 and self.user_input[i - 1] == "\\"
            if i > 1:
                # The backslash is escaped if the previous character is not a backslash
                # and the character before that is not a backslash
                is_escaped = is_escaped and not self.user_input[i - 2] == "\\"

            # Call the current state handler
            self._execute_current_state_handler(is_escaped, i)

        # Call the current state handler one last time to handle the last part
        self._execute_current_state_handler(is_escaped, len(self.user_input))

        self._add_to_pipeline()
        return self.pipeline

    def _add_to_pipeline(self):
        self.pipeline.append(
            UserInput(self.current_parts, self.current_out_file, self.current_err_file)
        )
        self.current_parts = []
        self.current_out_file = None
        self.current_err_file = None

    def _execute_current_state_handler(self, is_escaped: bool, position: int):
        current_state = self.states[self.state_stack[-1]]
        current_state(is_escaped, position)

    def _go_to_state(self, state_name: str):
        if state_name not in self.states:
            raise ValueError(f"Unknown state: {state_name}")

        self.state_stack.append(state_name)

    def _pop_state(self):
        if len(self.state_stack) > 1:
            self.state_stack.pop()
        else:
            raise ValueError("Cannot pop the last state from the stack")

    def _pop_and_go_to_state(self, state_name: str):
        self._pop_state()
        self._go_to_state(state_name)

    def _expand_glob_pattern(self, original_arg: str) -> List[str]:
        if any(char in original_arg for char in "*?["):  # Check for glob wildcards
            globbed_results = glob.glob(original_arg)
            if globbed_results:
                return globbed_results

        return [original_arg]

    def _save_current_part(self, apply_globbing=False):
        if self.current_part:
            # If we have a current part, add it to the list of parts
            # But first let's expand what needs to be expanded
            part = os.path.expanduser(self.current_part)
            if apply_globbing:
                parts = self._expand_glob_pattern(part)
            else:
                parts = [part]

            self.current_parts.extend(parts)
            self.current_part = ""

    def _default_state_handler(self, is_escaped: bool, position: int):
        # If we are at the end of the input, add the current part to the list of parts
        if position == len(self.user_input):
            self._save_current_part(apply_globbing=True)
            return

        if self.user_input[position] == "\\" and not is_escaped:
            return

        if self.user_input[position] == " " and not is_escaped:
            self._save_current_part(apply_globbing=True)
            return

        if self.user_input[position] == "'" and not is_escaped:
            self._go_to_state("single_quote")
            self._save_current_part(apply_globbing=True)
            return

        if self.user_input[position] == '"' and not is_escaped:
            self._go_to_state("double_quote")
            self._save_current_part(apply_globbing=True)
            return

        if self.user_input[position] == ">" and not is_escaped:
            self._go_to_state("inter_redirect")
            return

        if self.user_input[position] == "$" and not is_escaped:
            if self.user_input[position - 1] == " ":
                self._save_current_part(apply_globbing=True)
            self._go_to_state("env_variable")
            return

        if self.user_input[position] == "|" and not is_escaped:
            self._save_current_part(apply_globbing=True)
            self._add_to_pipeline()
            return

        self.current_part += self.user_input[position]

    def _single_quote_state_handler(self, is_escaped: bool, position: int):
        if position == len(self.user_input):
            return

        if self.user_input[position] == "'" and not is_escaped:
            self._pop_state()
            self._save_current_part()
            return

        self.current_part += self.user_input[position]

    def _double_quote_state_handler(self, is_escaped: bool, position: int):
        if position == len(self.user_input):
            return

        if is_escaped:
            # Double quotes preserves the special meaning of the backslash,
            # only when it is followed by \, $, " or newline
            if self.user_input[position] not in ["\\", "$", '"', "\n"]:
                self.current_part += "\\"
                is_escaped = False

        if self.user_input[position] == "\\" and not is_escaped:
            return

        if self.user_input[position] == '"' and not is_escaped:
            self._pop_state()
            self._save_current_part()
            return

        if self.user_input[position] == "$" and not is_escaped:
            self._go_to_state("env_variable")
            return

        self.current_part += self.user_input[position]

    def _intermediary_redirect_state_handler(self, is_escaped: bool, position: int):
        # This state is used to handle the intermediary part of a redirection
        # If the very first char is another '>', then we are dealing with an append redirection
        if self.user_input[position] == ">":
            self._save_current_part()
            self._pop_and_go_to_state("append_redirect")
        else:
            # This is a normal redirection. We need to check whether it is for the out or err stream
            is_error_redirect = False
            if self.current_part == "2":
                self.current_part = ""
                is_error_redirect = True
            elif self.current_part == "1":
                self.current_part = ""

            self._save_current_part()

            # And make sure we don't miss the current character
            self.current_part += self.user_input[position]
            self._pop_and_go_to_state(
                "error_redirect" if is_error_redirect else "out_redirect"
            )

    def _append_redirect_state_handler(self, is_escaped: bool, position: int):
        self._redirect_state_handler(is_escaped, position, "a", is_error=False)

    def _error_redirect_state_handler(self, is_escaped: bool, position: int):
        self._redirect_state_handler(is_escaped, position, "w", is_error=True)

    def _out_redirect_state_handler(self, is_escaped: bool, position: int):
        self._redirect_state_handler(is_escaped, position, "w", is_error=False)

    def _redirect_state_handler(
        self, is_escaped: bool, position: int, mode: FileMode, is_error: bool
    ):
        if position == len(self.user_input) or (
            (self.user_input[position] == " " and len(self.current_part.strip()) > 0)
            and not is_escaped
        ):
            # Here we are either coming from one of the quotes states, or finished readiing
            # the output file name. Save the current part (if we are coming from a quote state it
            # will be a no op as the the part would have already been saved), and pop it to use as
            # as the file name

            self._save_current_part()
            last_part = self.current_parts.pop().strip()
            if is_error:
                self.current_err_file = (last_part, mode)
            else:
                self.current_out_file = (last_part, mode)
            self._pop_state()
            return

        if self.user_input[position] == "\\" and not is_escaped:
            return

        if self.user_input[position] == "'" and not is_escaped:
            self._go_to_state("single_quote")
            return

        if self.user_input[position] == '"' and not is_escaped:
            self._go_to_state("double_quote")
            return

        self.current_part += self.user_input[position]

    def _env_variable_state_handler(self, is_escaped: bool, position: int):
        # We check for the end before the last char because we need the previous state
        # to handle the next char (or EOL).
        end_chars = [" ", '"']  # variable finishes after a space, double quotes or EOL
        found_end = (
            position + 1 < len(self.user_input)
            and self.user_input[position + 1] in end_chars
        ) or (position == len(self.user_input) - 1)

        if found_end:
            # Since we check the before the last char, make sure to add it to the variable name
            self.env_variable += self.user_input[position]
            expanded_variable = ""
            if self.env_variable in os.environ:
                expanded_variable = os.environ[self.env_variable]

            self.current_part += expanded_variable
            self.env_variable = ""
            self._pop_state()
            return

        self.env_variable += self.user_input[position]


class PyShell:
    PYSHELL_CONFIG_FILE = ".pyShell"

    def __init__(self):
        self.prompt = "$"
        self.builtin_commands_factory: Dict[str, CommandFactory] = {
            EchoCommand.NAME: CommandFactory(EchoCommand),
            ExitCommand.NAME: CommandFactory(ExitCommand, self),
            TypeCommand.NAME: CommandFactory(TypeCommand, self),
            PwdCommand.NAME: CommandFactory(PwdCommand),
            CdCommand.NAME: CommandFactory(CdCommand, self),
            HistoryCommand.NAME: CommandFactory(HistoryCommand, self),
            DoCommand.NAME: CommandFactory(DoCommand, self),
            ExplainCommand.NAME: CommandFactory(ExplainCommand, self),
        }
        self._last_dir = os.getcwd()
        self._cached_available_items = set()
        self.history_session_start = 0
        self.last_apended_history_item = 0
        self.config = {}
        self._on_load()

    # This is intended to show (print) messages to the shell always (and not redirect to any stream)
    def show_intenral_message(self, message: str):
        print(f"\033[90m > {message} \033[0m")


    def _get_pyshell_config_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), self.PYSHELL_CONFIG_FILE)

    def _load_pyshell_config(self):
        config_file_path = self._get_pyshell_config_path()
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, "r") as f:
                    self.config = json.load(f)
            except Exception as e:
                self.config = {}

    def _save_pyshell_config(self):
        config_file_path = self._get_pyshell_config_path()
        try:
            with open(config_file_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            # Do nothing if we can't save the config
            pass

    def update_config(self, key: str, value):
        self.config[key] = value
        self._save_pyshell_config()

    def _on_load(self):
        self._load_pyshell_config()
        if "HISTFILE" in os.environ:
            hist_file = os.environ["HISTFILE"]
            readline.read_history_file(hist_file)
            self.history_session_start = readline.get_current_history_length()

    def _on_unload(self):
        if "HISTFILE" in os.environ:
            hist_file = os.environ["HISTFILE"]
            nelements = (
                readline.get_current_history_length() - self.history_session_start
            )
            readline.append_history_file(nelements, hist_file)

    def _find_command(self, command_name: str) -> CommandFactory:
        # First check if the command is a built-in command
        if command_name in self.builtin_commands_factory:
            return self.builtin_commands_factory[command_name]

        # Then check if the command is an external command
        command_path = None
        path_env = os.environ["PATH"].split(":")
        for path_entry in path_env:
            if os.path.isdir(path_entry):
                for path_file in os.listdir(path_entry):
                    full_path_file = os.path.join(path_entry, path_file)
                    if (
                        command_name == path_file
                        and os.path.isfile(full_path_file)
                        and os.access(full_path_file, os.X_OK)
                    ):
                        command_path = full_path_file
                        break
            elif (
                os.path.isfile(path_entry)
                and command_name == os.path.basename(path_entry)
                and os.access(path_entry, os.X_OK)
            ):
                command_path = path_entry
                break

        if command_path:
            return CommandFactory(ExecutableCommand, command_path)

        # If the command is not found, return a CommandNotFound factory
        return CommandFactory(CommandNotFound, command_name)

    def _find_executables_in_path(self, command_prefix: str) -> List[str]:
        potential_executables = set()  # Use a set to avoid duplicates
        path_env = os.environ["PATH"].split(":")

        for path_entry in path_env:
            if os.path.isdir(path_entry):
                for path_file in os.listdir(path_entry):
                    full_path_file = os.path.join(path_entry, path_file)
                    if (
                        path_file.startswith(command_prefix)
                        and os.path.isfile(full_path_file)
                        and os.access(full_path_file, os.X_OK)
                    ):
                        potential_executables.add(path_file)
            elif (
                os.path.isfile(path_entry)
                and os.path.basename(path_entry).startswith(command_prefix)
                and os.access(path_entry, os.X_OK)
            ):
                potential_executables.add(os.path.basename(path_entry))

        return list(potential_executables)

    def _handle_tab_completion(self, text: str, state: int) -> Optional[str]:
        current_inut_line = readline.get_line_buffer()
        input_line_parts = current_inut_line.split(" ")
        is_argument_completion = len(input_line_parts) > 1
        last_input_part = input_line_parts[-1]

        # Build the suggestions only the first time and cache them
        if state == 0:
            if "/" in last_input_part:
                # If the last part contains a "/", we are completing a path
                last_input_part = os.path.expanduser(last_input_part)
                directory_path = os.path.dirname(last_input_part)

                local_files = os.listdir(directory_path)
                local_files = [file for file in local_files if file.startswith(text)]
                self._cached_available_items = set(local_files)
            elif is_argument_completion:
                # If we are completing an argument, we only need to list the local files
                # that start with the text
                local_files = os.listdir(os.getcwd())
                local_files = [file for file in local_files if file.startswith(text)]
                self._cached_available_items = set(local_files)
            else:
                # 1 - List the potential builtin commands
                builtin_commands = list(self.builtin_commands_factory.keys())
                builtin_commands = [
                    cmd for cmd in builtin_commands if cmd.startswith(text)
                ]

                # 2 - List the potential local files
                local_files = os.listdir(os.getcwd())
                local_files = [file for file in local_files if file.startswith(text)]

                # 3 - List the potential path files
                path_files = []
                if text:
                    path_files = self._find_executables_in_path(text)

                # 4 - Combine all suggestions
                self._cached_available_items = set(
                    builtin_commands + local_files + path_files
                )

        suggestions = list(self._cached_available_items)
        if len(suggestions) > state:
            trailing_char = ""

            # If there is only one suggestion, add a trailing space for files/executables
            # or a "/" for directories.
            if len(suggestions) == 1:
                suggestion = suggestions[0]
                # Determine the full path of the potential completion item to check if it's a directory.
                path_to_check = suggestion
                if "/" in last_input_part:
                    path_to_check = os.path.join(
                        os.path.dirname(last_input_part), suggestion
                    )

                if os.path.isdir(path_to_check):
                    trailing_char = "/"
                else:
                    trailing_char = " "

            return suggestions[state] + trailing_char

        return None

    def exit(self, exit_code):
        self._on_unload()
        sys.exit(exit_code)

    # This is the "Read-Eval-Print Loop" (REPL) method
    def repl(self):
        readline.set_completer(self._handle_tab_completion)
        readline.parse_and_bind("tab: complete")

        while True:
            input_line = input(f"{self.prompt} ")

            if not input_line:
                continue

            command, args = self._eval(input_line)
            try:
                command.execute(args)
            except CommandError as e:
                print(f"{command.name}: {e}", file=command.err_stream)
            finally:
                command.tear_down()

    def _eval(self, user_input: str) -> Tuple[Command, List[str]]:
        input_parser = InputParser(user_input)
        user_inputs = input_parser.parse()

        commands: List[Tuple[Command, List[str]]] = []
        for ui in user_inputs:
            # Keep it simple. If the first part of the user input is a variable assignment
            # just ignore the rest. Let's handle only the assignment
            if "=" in ui.input_parts[0]:
                assignment = ui.input_parts[0].split("=")
                if len(assignment) == 2:
                    assignment_command = AssignmentCommand(assignment[0], assignment[1])
                    return assignment_command, []

            cmd_factory = self._find_command(ui.input_parts[0])
            cmd_args = ui.input_parts[1:] if len(ui.input_parts) > 1 else []

            out_stream = None
            err_stream = None
            if ui.output_file:
                filename, mode = ui.output_file
                out_stream = open(filename, mode)

            if ui.error_file:
                filename, mode = ui.error_file
                err_stream = open(filename, mode)

            cmd = cmd_factory.make(out_stream=out_stream, err_stream=err_stream)
            commands.append((cmd, cmd_args))

        if len(commands) > 1:
            return PipelineCommand(commands), []

        return commands[0]


def main():
    shell = PyShell()
    shell.repl()


if __name__ == "__main__":
    main()
