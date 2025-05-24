#!/usr/bin/env python

class PyShell:
    def __init__(self):
        self.prompt = "$"

    # This is the "Read-Eval-Print Loop" (REPL) method
    def repl(self):
        while True:
            user_input = input(f"{self.prompt} ")

            if not user_input:
                continue

            # TODO
            self.eval(user_input)

    def eval(self, user_input):
        pass

def main():
    shell = PyShell()
    shell.repl()

if __name__ == "__main__":
    main()