import unittest
import unittest.mock
import sys
import os

from unittest.mock import patch, mock_open, ANY
from pyShell import (
    PyShell,
    CommandError,
    CommandNotFound,
    UserInput,
    InputParser,
    EchoCommand,
    PipelineCommand,
    AssignmentCommand
)


class TestPyShell(unittest.TestCase):
    def setUp(self):
        self.shell = PyShell()

    @patch("builtins.print")
    def test_echo_command(self, mock_print):
        command = self.shell._find_command("echo").make()
        command.execute(["Hello", "World"])
        mock_print.assert_called_once_with("Hello World", file=ANY)

    @patch("sys.exit")
    def test_exit_command(self, mock_exit):
        command = self.shell._find_command("exit").make()
        command.execute(["0"])
        mock_exit.assert_called_once_with(0)

    @patch("sys.exit")
    def test_exit_command_with_error_code(self, mock_exit):
        command = self.shell._find_command("exit").make()
        command.execute(["127"])
        mock_exit.assert_called_once_with(127)

    @patch("sys.exit")
    def test_exit_command_without_args(self, mock_exit):
        command = self.shell._find_command("exit").make()
        command.execute([])
        mock_exit.assert_called_once_with(0)

    def test_exit_command_invalid_argument(self):
        command = self.shell._find_command("exit").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["invalid"])
        self.assertEqual(str(context.exception), "invalid: numeric argument required")

    @patch("builtins.print")
    def test_type_command_builtin(self, mock_print):
        command = self.shell._find_command("type").make()
        command.execute(["echo"])
        mock_print.assert_called_once_with("echo is a shell builtin", file=ANY)

    @patch("builtins.print")
    def test_type_command_builtin_multile_args(self, mock_print):
        command = self.shell._find_command("type").make()
        command.execute(["echo", "exit"])
        mock_print.assert_has_calls(
            [
                unittest.mock.call("echo is a shell builtin", file=ANY),
                unittest.mock.call("exit is a shell builtin", file=ANY),
            ],
            any_order=False,
        )
        self.assertEqual(mock_print.call_count, 2)

    @patch("builtins.print")
    def test_type_command_not_found(self, mock_print):
        command = self.shell._find_command("type").make()
        command.execute(["nonexistent"])
        mock_print.assert_called_once_with("nonexistent: not found", file=ANY)

    @patch("builtins.print")
    def test_command_not_found(self, mock_print):
        command = self.shell._find_command("nonexistent").make()
        command.execute([])
        mock_print.assert_called_once_with("nonexistent: Command not found", file=ANY)

    @patch.dict("os.environ", {"PATH": "/mock/bin/ls"}, clear=True)
    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=True)
    @patch("subprocess.run")
    def test_executable_command(self, mock_run, mock_access, mock_isfile):
        command = self.shell._find_command("ls").make()
        command.execute(["-l"])
        mock_run.assert_called_once_with(
            ["ls", "-l"], stdout=ANY, stderr=ANY, stdin=ANY
        )

    @patch.dict("os.environ", {"PATH": "/mock/bin/"}, clear=True)
    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=True)
    @patch("subprocess.run")
    @patch("builtins.print")
    def test_executable_command_not_found(
        self, mock_print, mock_run, mock_access, mock_isfile
    ):
        command = self.shell._find_command("ls").make()
        command.execute(["-l"])
        self.assertTrue(isinstance(command, CommandNotFound))
        mock_run.assert_not_called()

    @patch.dict("os.environ", {"PATH": "/mock/bin/ls"}, clear=True)
    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=False)
    @patch("subprocess.run")
    @patch("builtins.print")
    def test_executable_command_not_executable_file(
        self, mock_print, mock_run, mock_access, mock_isfile
    ):
        command = self.shell._find_command("ls").make()
        command.execute(["-l"])
        self.assertTrue(isinstance(command, CommandNotFound))
        mock_run.assert_not_called()

    @patch("builtins.print")
    def test_pwd_command(self, mock_print):
        command = self.shell._find_command("pwd").make()
        command.execute([])
        mock_print.assert_called_once_with(os.getcwd(), file=ANY)

    @patch("os.chdir")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.isdir", return_value=True)
    def test_cd_command(self, mock_isdir, mock_exists, mock_chdir):
        command = self.shell._find_command("cd").make()
        command.execute(["/mock/new_dir"])
        mock_chdir.assert_called_once_with("/mock/new_dir")

    @patch("os.chdir")
    @patch("os.getcwd", side_effect=["/mock/old_dir", "/mock/new_dir"])
    def test_cd_command_with_dash(self, mock_getcwd, mock_chdir):
        self.shell._last_dir = "/mock/old_dir"
        command = self.shell._find_command("cd").make()
        command.execute(["-"])
        mock_chdir.assert_called_once_with("/mock/old_dir")

    @patch("os.path.isdir", return_value=False)
    @patch("os.path.exists", return_value=True)
    def test_cd_command_not_a_directory(self, mock_exists, mock_isdir):
        command = self.shell._find_command("cd").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["/mock/file"])
        self.assertEqual(str(context.exception), "/mock/file: Not a directory")

    @patch("os.path.exists", return_value=False)
    def test_cd_command_no_such_file_or_directory(self, mock_exists):
        command = self.shell._find_command("cd").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["/mock/nonexistent"])
        self.assertEqual(
            str(context.exception), "/mock/nonexistent: No such file or directory"
        )

    @patch("os.path.expanduser", return_value="/mock/home")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.isdir", return_value=True)
    @patch("os.chdir")
    def test_cd_command_home_directory(
        self, mock_chdir, mock_isdir, mock_exists, mock_expanduser
    ):
        command = self.shell._find_command("cd").make()
        command.execute([])
        mock_expanduser.assert_called_once_with("~")
        mock_chdir.assert_called_once_with("/mock/home")

    @patch.dict("os.environ", {"PATH": ""}, clear=True)
    def test_handle_tab_completion_builtin_commands(self):
        # Simulate tab completion for an empty input
        result = []
        for state in range(10):  # Arbitrary large number to exhaust suggestions
            suggestion = self.shell._handle_tab_completion("e", state)
            if suggestion is None:
                break
            result.append(suggestion)

        expected = [
            cmd
            for cmd in self.shell.builtin_commands_factory.keys()
            if cmd.startswith("e")
        ]
        self.assertEqual(sorted(result), sorted(expected))

    @patch.dict("os.environ", {"PATH": "/mock/bin"}, clear=True)
    @patch(
        "os.listdir",
        side_effect=lambda path: {"/mock/bin": ["cmd1", "cmd2"]}.get(path, []),
    )
    @patch("os.path.isdir", side_effect=lambda path: path in ["/mock/bin"])
    @patch(
        "os.path.isfile",
        side_effect=lambda path: path in ["/mock/bin/cmd1", "/mock/bin/cmd2"],
    )
    @patch(
        "os.access",
        side_effect=lambda path, mode: path in ["/mock/bin/cmd1", "/mock/bin/cmd2"],
    )
    def test_handle_tab_completion_commands_and_path(
        self, mock_access, mock_isfile, mock_isdir, mock_listdir
    ):
        # Simulate tab completion for an empty input
        result = []
        for state in range(10):  # Arbitrary large number to exhaust suggestions
            suggestion = self.shell._handle_tab_completion("c", state)
            if suggestion is None:
                break
            result.append(suggestion)

        expected_builtin = [
            cmd
            for cmd in self.shell.builtin_commands_factory.keys()
            if cmd.startswith("c")
        ]
        expected = ["cmd1", "cmd2"] + expected_builtin
        self.assertEqual(sorted(result), sorted(expected))

    @patch.dict("os.environ", {"PATH": ""}, clear=True)
    @patch("os.listdir", side_effect=lambda path: ["file1", "file2", "cmd1"])
    @patch("os.getcwd", side_effect=lambda: "mock")
    def test_handle_tab_completion_commands_and_files(self, mock_getcwd, mock_listdir):
        # Simulate tab completion for an empty input
        result = []
        for state in range(10):  # Arbitrary large number to exhaust suggestions
            suggestion = self.shell._handle_tab_completion("f", state)
            if suggestion is None:
                break
            result.append(suggestion)

        expected_builtin = [
            cmd
            for cmd in self.shell.builtin_commands_factory.keys()
            if cmd.startswith("f")
        ]
        expected = ["file1", "file2"] + expected_builtin
        self.assertEqual(sorted(result), sorted(expected))

    @patch.dict("os.environ", {"PATH": "/mock/bin:/mock/usr/bin"}, clear=True)
    @patch(
        "os.listdir",
        side_effect=lambda path: {
            "/mock/bin": ["cmd1", "cmd2", "not_executable"],
            "/mock/usr/bin": ["cmd3", "cmd4"],
        }.get(path, []),
    )
    @patch(
        "os.path.isfile",
        side_effect=lambda path: path
        in [
            "/mock/bin/cmd1",
            "/mock/bin/cmd2",
            "/mock/usr/bin/cmd3",
            "/mock/usr/bin/cmd4",
        ],
    )
    @patch(
        "os.access",
        side_effect=lambda path, mode: path
        in [
            "/mock/bin/cmd1",
            "/mock/bin/cmd2",
            "/mock/usr/bin/cmd3",
            "/mock/usr/bin/cmd4",
        ],
    )
    @patch(
        "os.path.isdir", side_effect=lambda path: path in ["/mock/bin", "/mock/usr/bin"]
    )
    def test_find_executables_in_path(
        self, mock_isdir, mock_access, mock_isfile, mock_listdir
    ):
        result = self.shell._find_executables_in_path("cmd")
        expected = ["cmd1", "cmd2", "cmd3", "cmd4"]
        self.assertEqual(sorted(result), sorted(expected))

    @patch.dict("os.environ", {"PATH": "/mock/bin:/mock/usr/bin"}, clear=True)
    @patch(
        "os.listdir",
        side_effect=lambda path: {
            "/mock/bin": ["cmd1", "cmd2"],
            "/mock/usr/bin": ["cmd3", "cmd4"],
        }.get(path, []),
    )
    @patch(
        "os.path.isfile",
        side_effect=lambda path: path
        in [
            "/mock/bin/cmd1",
            "/mock/bin/cmd2",
            "/mock/usr/bin/cmd3",
            "/mock/usr/bin/cmd4",
        ],
    )
    @patch(
        "os.access",
        side_effect=lambda path, mode: path
        in [
            "/mock/bin/cmd1",
            "/mock/bin/cmd2",
            "/mock/usr/bin/cmd3",
            "/mock/usr/bin/cmd4",
        ],
    )
    @patch(
        "os.path.isdir", side_effect=lambda path: path in ["/mock/bin", "/mock/usr/bin"]
    )
    def test_find_executables_in_path_partial_match(
        self, mock_isdir, mock_access, mock_isfile, mock_listdir
    ):
        result = self.shell._find_executables_in_path("cmd3")
        expected = ["cmd3"]
        self.assertEqual(result, expected)

    @patch("readline.get_current_history_length", return_value=5)
    @patch(
        "readline.get_history_item",
        side_effect=lambda i: f"command{i}" if i <= 5 else None,
    )
    @patch("builtins.print")
    def test_history_command_full_history(
        self, mock_print, mock_get_history_item, mock_get_history_length
    ):
        command = self.shell._find_command("history").make()
        command.execute([])
        mock_print.assert_has_calls(
            [
                unittest.mock.call("\t1  command1", file=ANY),
                unittest.mock.call("\t2  command2", file=ANY),
                unittest.mock.call("\t3  command3", file=ANY),
                unittest.mock.call("\t4  command4", file=ANY),
                unittest.mock.call("\t5  command5", file=ANY),
            ],
            any_order=False,
        )

    @patch("readline.get_current_history_length", return_value=5)
    @patch(
        "readline.get_history_item",
        side_effect=lambda i: f"command{i}" if i <= 5 else None,
    )
    @patch("builtins.print")
    def test_history_command_with_arg(
        self, mock_print, mock_get_history_item, mock_get_history_length
    ):
        command = self.shell._find_command("history").make()
        command.execute(["3"])
        mock_print.assert_has_calls(
            [
                unittest.mock.call("\t3  command3", file=ANY),
                unittest.mock.call("\t4  command4", file=ANY),
                unittest.mock.call("\t5  command5", file=ANY),
            ],
            any_order=False,
        )

    @patch("readline.get_current_history_length", return_value=5)
    @patch(
        "readline.get_history_item",
        side_effect=lambda i: f"command{i}" if i <= 5 else None,
    )
    def test_history_command_invalid_arg(
        self, mock_get_history_item, mock_get_history_length
    ):
        command = self.shell._find_command("history").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["invalid"])
        self.assertEqual(str(context.exception), "invalid: numeric argument required")

    @patch("readline.get_current_history_length", return_value=5)
    @patch(
        "readline.get_history_item",
        side_effect=lambda i: f"command{i}" if i <= 5 else None,
    )
    def test_history_command_too_many_args(
        self, mock_get_history_item, mock_get_history_length
    ):
        command = self.shell._find_command("history").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["2", "3"])
        self.assertEqual(str(context.exception), "too many arguments")

    def test_parse_input_simple(self):
        self.assertEqual(
            InputParser("exit").parse(),
            [UserInput(input_parts=["exit"], output_file=None, error_file=None)],
        )

    def test_parse_input_simple_with_args(self):
        self.assertEqual(
            InputParser("echo Hello, World!").parse(),
            [
                UserInput(
                    input_parts=["echo", "Hello,", "World!"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_simple_with_args2(self):
        self.assertEqual(
            InputParser("cd ..").parse(),
            [UserInput(input_parts=["cd", ".."], output_file=None, error_file=None)],
        )

    def test_parse_input_simple_with_flag_args(self):
        self.assertEqual(
            InputParser("ls -l /home/user").parse(),
            [
                UserInput(
                    input_parts=["ls", "-l", "/home/user"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_empty(self):
        self.assertEqual(
            InputParser("").parse(),
            [UserInput(input_parts=[], output_file=None, error_file=None)],
        )

    def test_parse_input_spaces(self):
        self.assertEqual(
            InputParser("      ").parse(),
            [UserInput(input_parts=[], output_file=None, error_file=None)],
        )

    def test_parse_input_with_escape_space(self):
        self.assertEqual(
            InputParser(r"echo Hello\ World").parse(),
            [
                UserInput(
                    input_parts=["echo", "Hello World"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_with_escape_backslash(self):
        self.assertEqual(
            InputParser(r"echo Hello\\World").parse(),
            [
                UserInput(
                    input_parts=["echo", "Hello\\World"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_single_quote_basic(self):
        self.assertEqual(
            InputParser("echo 'Hello, World!'").parse(),
            [
                UserInput(
                    input_parts=["echo", "Hello, World!"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_single_quote_with_double_quote(self):
        self.assertEqual(
            InputParser("echo 'Hello, \"World!\"'").parse(),
            [
                UserInput(
                    input_parts=["echo", 'Hello, "World!"'],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_single_quote_with_double_backlash(self):
        self.assertEqual(
            InputParser(r"echo 'a \$ b'").parse(),
            [
                UserInput(
                    input_parts=["echo", r"a \$ b"], output_file=None, error_file=None
                )
            ],
        )
        self.assertEqual(
            InputParser(r"echo 'a \ b'").parse(),
            [
                UserInput(
                    input_parts=["echo", r"a \ b"], output_file=None, error_file=None
                )
            ],
        )
        self.assertEqual(
            InputParser("echo 'a \\\" b'").parse(),
            [
                UserInput(
                    input_parts=["echo", r"a \" b"], output_file=None, error_file=None
                )
            ],
        )

    def test_parse_input_double_quote_basic(self):
        self.assertEqual(
            InputParser('echo "Hello, World!"').parse(),
            [
                UserInput(
                    input_parts=["echo", "Hello, World!"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_double_quote_with_escaped_quote(self):
        self.assertEqual(
            InputParser(r'echo "Hello, \"World!\""').parse(),
            [
                UserInput(
                    input_parts=["echo", r'Hello, "World!"'],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_double_quote_with_backslash(self):
        self.assertEqual(
            InputParser(r'echo "Hello, \World!"').parse(),
            [
                UserInput(
                    input_parts=["echo", r"Hello, \World!"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_double_quote_with_2backslashes(self):
        self.assertEqual(
            InputParser(r'echo "Hello, \\World!"').parse(),
            [
                UserInput(
                    input_parts=["echo", r"Hello, \World!"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_double_quote_with_single_quote(self):
        self.assertEqual(
            InputParser("echo \"Hello, 'World!'\"").parse(),
            [
                UserInput(
                    input_parts=["echo", "Hello, 'World!'"],
                    output_file=None,
                    error_file=None,
                )
            ],
        )

    def test_parse_input_redirect_output(self):
        self.assertEqual(
            InputParser("cat file.txt > out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "w"),
                    error_file=None,
                )
            ],
        )

    def test_parse_input_redirect_output_explicit(self):
        self.assertEqual(
            InputParser("cat file.txt 1> out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "w"),
                    error_file=None,
                )
            ],
        )

    def test_parse_input_redirect_output_with_escaped_space(self):
        self.assertEqual(
            InputParser("cat file\\ 2.txt > out\\ 2.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file 2.txt"],
                    output_file=("out 2.txt", "w"),
                    error_file=None,
                )
            ],
        )

    def test_parse_input_redirect_output_with_quotes(self):
        self.assertEqual(
            InputParser("cat 'file 2.txt' > 'out 2.txt'").parse(),
            [
                UserInput(
                    input_parts=["cat", "file 2.txt"],
                    output_file=("out 2.txt", "w"),
                    error_file=None,
                )
            ],
        )

    def test_parse_input_redirect_err(self):
        self.assertEqual(
            InputParser("cat file.txt 2> err.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=None,
                    error_file=("err.txt", "w"),
                )
            ],
        )

    def test_parse_input_redirect_err_with_escaped_space(self):
        self.assertEqual(
            InputParser("cat file\\ 2.txt 2> err\\ 2.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file 2.txt"],
                    output_file=None,
                    error_file=("err 2.txt", "w"),
                )
            ],
        )

    def test_parse_input_redirect_err_with_quotes(self):
        self.assertEqual(
            InputParser('cat "file 2.txt" 2> "err 2.txt"').parse(),
            [
                UserInput(
                    input_parts=["cat", "file 2.txt"],
                    output_file=None,
                    error_file=("err 2.txt", "w"),
                )
            ],
        )

    def test_parse_input_redirect_append_out(self):
        self.assertEqual(
            InputParser("cat file.txt >> append.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("append.txt", "a"),
                    error_file=None,
                )
            ],
        )

    def test_parse_input_redirect_output_different_spacing(self):
        self.assertEqual(
            InputParser("cat file.txt >out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "w"),
                    error_file=None,
                )
            ],
        )
        self.assertEqual(
            InputParser("cat file.txt>out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "w"),
                    error_file=None,
                )
            ],
        )
        self.assertEqual(
            InputParser("cat file.txt> out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "w"),
                    error_file=None,
                )
            ],
        )
        self.assertEqual(
            InputParser("cat file.txt>>out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "a"),
                    error_file=None,
                )
            ],
        )
        self.assertEqual(
            InputParser("cat file.txt>> out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "a"),
                    error_file=None,
                )
            ],
        )
        self.assertEqual(
            InputParser("cat file.txt >>out.txt").parse(),
            [
                UserInput(
                    input_parts=["cat", "file.txt"],
                    output_file=("out.txt", "a"),
                    error_file=None,
                )
            ],
        )

    def test_parse_input_pipe_2_commands(self):
        self.assertEqual(
            InputParser("command1 | command2").parse(),
            [
                UserInput(input_parts=["command1"], output_file=None, error_file=None),
                UserInput(input_parts=["command2"], output_file=None, error_file=None),
            ],
        )
        self.assertEqual(
            InputParser("command1|command2").parse(),
            [
                UserInput(input_parts=["command1"], output_file=None, error_file=None),
                UserInput(input_parts=["command2"], output_file=None, error_file=None),
            ],
        )

    def test_parse_input_pipe_multiple_commands(self):
        self.assertEqual(
            InputParser("command1 | command2 | command3 | command4").parse(),
            [
                UserInput(input_parts=["command1"], output_file=None, error_file=None),
                UserInput(input_parts=["command2"], output_file=None, error_file=None),
                UserInput(input_parts=["command3"], output_file=None, error_file=None),
                UserInput(input_parts=["command4"], output_file=None, error_file=None),
            ],
        )

    def test_parse_input_pipe_with_redirect(self):
        self.assertEqual(
            InputParser("command1 | command2 > tmp").parse(),
            [
                UserInput(input_parts=["command1"], output_file=None, error_file=None),
                UserInput(
                    input_parts=["command2"], output_file=("tmp", "w"), error_file=None
                ),
            ],
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("builtins.print")
    def test_command_redirect_output(self, mock_print, mock_open_file):
        # Simulate the "echo Hello > out.txt" command
        mock_out_stream = mock_open_file.return_value
        command = self.shell._find_command("echo").make(out_stream=mock_out_stream)
        command.execute(["Hello"])

        # Verify that the output was written to the file
        mock_print.assert_called_once_with("Hello", file=mock_out_stream)

    @patch("builtins.open", new_callable=mock_open)
    @patch("builtins.print")
    def test_command_redirect_error(self, mock_print, mock_open_file):
        # Simulate the "echo Hello > out.txt" command
        mock_err_stream = mock_open_file.return_value
        command = self.shell._find_command("type").make(err_stream=mock_err_stream)
        command.execute(["invalidCommand"])

        # Verify that the output was written to the file
        mock_print.assert_called_once_with(
            "invalidCommand: not found", file=mock_err_stream
        )

    @patch("pyShell.InputParser")
    def test_eval_normal_command(self, mock_input_parser):
        mock_input_parser.return_value.parse.return_value = [
            UserInput(input_parts=["echo", "Hello, World!"])
        ]

        command, args = self.shell._eval("echo Hello, World!")

        self.assertTrue(isinstance(command, EchoCommand))
        self.assertEqual(args, ["Hello, World!"])

    @patch("pyShell.InputParser")
    def test_eval_pipeline_command(self, mock_input_parser):
        mock_input_parser.return_value.parse.return_value = [
            UserInput(input_parts=["echo", "Hello, World!"]),
            UserInput(input_parts=["wc"])
        ]

        command, args = self.shell._eval("echo Hello, World!")

        self.assertTrue(isinstance(command, PipelineCommand))
        self.assertEqual(args, [])

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion(self):
        result = InputParser("echo $HOME").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "/mock/home"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_text_after(self):
        result = InputParser("echo $HOME aaa").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "/mock/home", "aaa"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_text_before_space(self):
        result = InputParser("echo aa $HOME").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "aa", "/mock/home"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_text_before_no_space(self):
        result = InputParser("echo aa$HOME").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "aa/mock/home"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_parse_input_env_var_expansion_not_found(self):
        result = InputParser("echo $HOME").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_parse_input_env_var_expansion_not_found_text_before_space(self):
        result = InputParser("echo aa $HOME").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "aa"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_parse_input_env_var_expansion_not_found_text_before_no_space(self):
        result = InputParser("echo aa$HOME").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "aa"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_parse_input_env_var_expansion_not_found_text_after(self):
        result = InputParser("echo $HOME aa").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "aa"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_dquotes(self):
        result = InputParser('echo "$HOME"').parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "/mock/home"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_text_after_dquotes(self):
        result = InputParser('echo "$HOME aaa"').parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "/mock/home aaa"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_text_before_space_dquotes(self):
        result = InputParser('echo "aa $HOME"').parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "aa /mock/home"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_text_before_no_space_dquotes(self):
        result = InputParser('echo "aa$HOME"').parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "aa/mock/home"], output_file=None, error_file=None)]
        )

    @patch.dict(os.environ, {"HOME": "/mock/home"}, clear=True)
    def test_parse_input_env_var_expansion_squotes(self):
        # Inside single quotes string, $ should not expand!
        result = InputParser("echo '$HOME'").parse()
        self.assertEqual(
            result,
            [UserInput(input_parts=["echo", "$HOME"], output_file=None, error_file=None)]
        )

    def test_eval_variable_assignment_returns_assignment_command(self):
        command, args = self.shell._eval("ABC=5")
        self.assertIsInstance(command, AssignmentCommand)

        if isinstance(command, AssignmentCommand):
            self.assertEqual(command.var_name, "ABC")
            self.assertEqual(command.val, "5")
        self.assertEqual(args, [])

    @patch.dict(os.environ, {}, clear=True)
    def test_variable_assignment_sets_env(self):
        command, args = self.shell._eval("ABC=5")
        command.execute(args)
        self.assertEqual(os.environ.get("ABC"), "5")

    @patch("readline.read_history_file")
    def test_history_read_flag(self, mock_read_history_file):
        command = self.shell._find_command("history").make()
        command.execute(["-r", "histfile.txt"])
        mock_read_history_file.assert_called_once_with("histfile.txt")

    @patch("readline.write_history_file")
    def test_history_write_flag(self, mock_write_history_file):
        command = self.shell._find_command("history").make()
        command.execute(["-w", "histfile.txt"])
        mock_write_history_file.assert_called_once_with("histfile.txt")

    @patch("readline.append_history_file")
    @patch("readline.get_current_history_length", return_value=10)
    def test_history_append_flag(self, mock_get_history_length, mock_append_history_file):
        self.shell.last_apended_history_item = 0
        command = self.shell._find_command("history").make()
        command.execute(["-a", "histfile.txt"])
        mock_append_history_file.assert_called_once_with(10, "histfile.txt")
        # Also make sure the 'last_apended_history_item' is updated with the
        # value returned from readline
        self.assertEqual(10, self.shell.last_apended_history_item)

    @patch("readline.append_history_file")
    @patch("readline.get_current_history_length", return_value=10)
    def test_history_append_flag_second_time(self, mock_get_history_length, mock_append_history_file):
        self.shell.last_apended_history_item = 5
        command = self.shell._find_command("history").make()
        command.execute(["-a", "histfile.txt"])
        mock_append_history_file.assert_called_once_with(5, "histfile.txt")
        # Also make sure the 'last_apended_history_item' is updated with the
        # value returned from readline
        self.assertEqual(10, self.shell.last_apended_history_item)


    def test_history_read_flag_without_filename(self):
        command = self.shell._find_command("history").make()
        with self.assertRaises(CommandError) as cm:
            command.execute(["-r"])
        self.assertEqual(str(cm.exception), "-r: file name required")

    def test_history_write_flag_without_filename(self):
        command = self.shell._find_command("history").make()
        with self.assertRaises(CommandError) as cm:
            command.execute(["-w"])
        self.assertEqual(str(cm.exception), "-w: file name required")

    def test_history_append_flag_without_filename(self):
        command = self.shell._find_command("history").make()
        with self.assertRaises(CommandError) as cm:
            command.execute(["-a"])
        self.assertEqual(str(cm.exception), "-a: file name required")

if __name__ == "__main__":
    unittest.main()
