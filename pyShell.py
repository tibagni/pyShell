#!/usr/bin/env python
import sys
import os
import subprocess
import readline  # type: ignore Keep this import to properly handle arrow keys in the input

from typing import List, Tuple, Dict, Callable, Type


class CommandError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:
        return self.message


class Command:
    def __init__(self, name: str):
        self.name = name

    def execute(self, args: List[str]):
        pass


class CommandNotFound(Command):
    def __init__(self, name: str):
        super().__init__(name)

    def execute(self, args: List[str]):
        print(f"{self.name}: Command not found", file=sys.stderr)


class ExecutableCommand(Command):
    def __init__(self, command_path: str):
        super().__init__(os.path.basename(command_path))
        self.command_path = command_path

    def execute(self, args: List[str]):
        cmd = [self.name]
        cmd.extend(args)
        subprocess.run(cmd)


class BuiltinCommand(Command):
    def __init__(self, name: str):
        super().__init__(name)


class EchoCommand(BuiltinCommand):
    NAME = "echo"

    def __init__(self):
        super().__init__(EchoCommand.NAME)

    def execute(self, args: List[str]):
        # TODO handle flag aruments
        print(" ".join(args))


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
                print(f"{arg} is a shell builtin")
            elif issubclass(command_factory.command_type, ExecutableCommand):
                # For executable commands, the first argument of the factory is the command path
                print(f"{arg} is {command_factory.args[0]}")
            else:
                print(f"{arg}: not found", file=sys.stderr)


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
        }

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

    # This is the "Read-Eval-Print Loop" (REPL) method
    def repl(self):
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
