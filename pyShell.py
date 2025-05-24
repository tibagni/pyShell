#!/usr/bin/env python
import sys
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
                print(f"{arg}: is a shell builtin")
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
        if command_name in self.builtin_commands_factory:
            return self.builtin_commands_factory[command_name]

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
