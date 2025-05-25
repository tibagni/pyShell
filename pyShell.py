#!/usr/bin/env python
import sys
import os
import subprocess
import readline  # type: ignore Keep this import to properly handle arrow keys in the input

from typing import List, Tuple, Dict, Type, Optional


class CommandError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return self.message


class Command:
    def __init__(self, name: str):
        self.name = name
        self.out_stream = sys.stdout
        self.err_stream = sys.stderr
        self.in_stream = sys.stdin

    def execute(self, args: List[str]):
        pass


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
        subprocess.run(cmd, stdout=self.out_stream, stderr=self.err_stream, stdin=self.in_stream)


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

    def __init__(self):
        super().__init__(ExitCommand.NAME)

    def execute(self, args: List[str]):
        exit_code = 0
        if args:
            try:
                exit_code = int(args[0])
            except ValueError:
                raise CommandError(f"{args[0]}: numeric argument required")

        sys.exit(exit_code)


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
            if issubclass(command_factory.command_type, BuiltinCommand):
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

class CommandFactory:
    def __init__(self, command_type: Type[Command], *args, **kwargs):
        self.command_type = command_type
        self.args = args
        self.kwargs = kwargs

    def make(self) -> Command:
        return self.command_type(*self.args, **self.kwargs)


class PyShell:
    def __init__(self):
        self.prompt = "$"
        self.builtin_commands_factory: Dict[str, CommandFactory] = {
            EchoCommand.NAME: CommandFactory(EchoCommand),
            ExitCommand.NAME: CommandFactory(ExitCommand),
            TypeCommand.NAME: CommandFactory(TypeCommand, self),
            PwdCommand.NAME: CommandFactory(PwdCommand),
            CdCommand.NAME: CommandFactory(CdCommand, self)
        }
        self._last_dir = os.getcwd()
        self._cached_available_items = set()

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
                        path_file.startswith(command_prefix) and
                        os.path.isfile(full_path_file) and
                        os.access(full_path_file, os.X_OK)
                    ):
                        potential_executables.add(path_file)
            elif (
                os.path.isfile(path_entry) and
                os.path.basename(path_entry).startswith(command_prefix) and
                os.access(path_entry, os.X_OK)
            ):
                potential_executables.add(os.path.basename(path_entry))

        return list(potential_executables)

    def _handle_tab_completion(self, text: str, state: int) -> Optional[str]:
        # TODO handle argument completion
        # TODO handle path completion
        # current_inut_line = readline.get_line_buffer()
        # input_line_parts = current_inut_line.split(" ")
        # is_argument_completion = len(input_line_parts) > 1

        # Build the suggestions only the first time and cache them
        if state == 0:
            # 1 - List the potential builtin commands
            builtin_commands = list(self.builtin_commands_factory.keys())
            builtin_commands = [cmd for cmd in builtin_commands if cmd.startswith(text)]

            # 2 - List the potential local files
            local_files = os.listdir(os.getcwd())
            local_files = [file for file in local_files if file.startswith(text)]

            # 3 - List the potential path files
            path_files = []
            if text:
                path_files = self._find_executables_in_path(text)

            # 4 - Combine all suggestions
            self._cached_available_items = set(builtin_commands + local_files + path_files)

        suggestions = list(self._cached_available_items)
        if len(suggestions) > state:
            # If there is only one suggestion, add a trailing space
            add_trailing_space = len(suggestions) == 1
            return suggestions[state] + (" " if add_trailing_space else "")

        return None


    # This is the "Read-Eval-Print Loop" (REPL) method
    def repl(self):
        readline.set_completer(self._handle_tab_completion)
        readline.parse_and_bind("tab: complete")

        while True:
            input_line = input(f"{self.prompt} ")

            if not input_line:
                continue

            # TODO
            command, args = self._eval(input_line)
            try:
                command.execute(args)
            except CommandError as e:
                print(f"{command.name}: {e}", file=sys.stderr)

    def _eval(self, user_input: str) -> Tuple[Command, List[str]]:
        parts = user_input.split()
        command_name = parts[0]
        command_args = parts[1:] if len(parts) > 1 else []

        command = self._find_command(command_name).make()
        return command, command_args


def main():
    shell = PyShell()
    shell.repl()


if __name__ == "__main__":
    main()