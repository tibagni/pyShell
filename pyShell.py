#!/usr/bin/env python
import sys
from typing import List, Tuple

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

class PyShell:
    def __init__(self):
        self.prompt = "$"
        self.builtin_commands = {
            EchoCommand.NAME: EchoCommand()
        }

    # This is the "Read-Eval-Print Loop" (REPL) method
    def repl(self):
        while True:
            input_line = input(f"{self.prompt} ")

            if not input_line:
                continue

            # TODO
            command, args = self.eval(input_line)
            try:
                command.execute(args)
            except Exception as e:
                print(f"Error executing command '{command.name}': {e}", file=sys.stderr)

    def eval(self, user_input: str) -> Tuple[Command, List[str]]:
        parts = user_input.split()
        command_name = parts[0]
        if command_name in self.builtin_commands:
            return (self.builtin_commands[command_name], parts[1:])

        return (CommandNotFound(command_name), [])

def main():
    shell = PyShell()
    shell.repl()

if __name__ == "__main__":
    main()