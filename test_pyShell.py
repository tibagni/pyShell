import unittest
import unittest.mock
import sys
import os

from unittest.mock import patch
from pyShell import PyShell, CommandError, CommandNotFound


class TestPyShell(unittest.TestCase):
    def setUp(self):
        self.shell = PyShell()

    @patch('builtins.print')
    def test_echo_command(self, mock_print):
        command = self.shell._find_command("echo").make()
        command.execute(["Hello", "World"])
        mock_print.assert_called_once_with("Hello World")

    @patch('sys.exit')
    def test_exit_command(self, mock_exit):
        command = self.shell._find_command("exit").make()
        command.execute(["0"])
        mock_exit.assert_called_once_with(0)

    @patch('sys.exit')
    def test_exit_command_with_error_code(self, mock_exit):
        command = self.shell._find_command("exit").make()
        command.execute(["127"])
        mock_exit.assert_called_once_with(127)

    @patch('sys.exit')
    def test_exit_command_without_args(self, mock_exit):
        command = self.shell._find_command("exit").make()
        command.execute([])
        mock_exit.assert_called_once_with(0)

    def test_exit_command_invalid_argument(self):
        command = self.shell._find_command("exit").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["invalid"])
        self.assertEqual(str(context.exception), "invalid: numeric argument required")

    @patch('builtins.print')
    def test_type_command_builtin(self, mock_print):
        command = self.shell._find_command("type").make()
        command.execute(["echo"])
        mock_print.assert_called_once_with("echo is a shell builtin")

    @patch('builtins.print')
    def test_type_command_builtin_multile_args(self, mock_print):
        command = self.shell._find_command("type").make()
        command.execute(["echo", "exit"])
        mock_print.assert_has_calls([
            unittest.mock.call("echo is a shell builtin"),
            unittest.mock.call("exit is a shell builtin")
        ], any_order=False)
        self.assertEqual(mock_print.call_count, 2)

    @patch('builtins.print')
    def test_type_command_not_found(self, mock_print):
        command = self.shell._find_command("type").make()
        command.execute(["nonexistent"])
        mock_print.assert_called_once_with("nonexistent: not found", file=sys.stderr)

    @patch('builtins.print')
    def test_command_not_found(self, mock_print):
        command = self.shell._find_command("nonexistent").make()
        command.execute([])
        mock_print.assert_called_once_with("nonexistent: Command not found", file=sys.stderr)

    @patch.dict('os.environ', {'PATH': '/mock/bin/ls'}, clear=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.access', return_value=True)
    @patch('subprocess.run')
    def test_executable_command(self, mock_run, mock_access, mock_isfile):
        command = self.shell._find_command("ls").make()
        command.execute(["-l"])
        mock_run.assert_called_once_with(["ls", "-l"])

    @patch.dict('os.environ', {'PATH': '/mock/bin/'}, clear=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.access', return_value=True)
    @patch('subprocess.run')
    @patch('builtins.print')
    def test_executable_command_not_found(self, mock_print, mock_run, mock_access, mock_isfile):
        command = self.shell._find_command("ls").make()
        command.execute(["-l"])
        self.assertTrue(isinstance(command, CommandNotFound))
        mock_run.assert_not_called()

    @patch.dict('os.environ', {'PATH': '/mock/bin/ls'}, clear=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.access', return_value=False)
    @patch('subprocess.run')
    @patch('builtins.print')
    def test_executable_command_not_executable_file(self, mock_print, mock_run, mock_access, mock_isfile):
        command = self.shell._find_command("ls").make()
        command.execute(["-l"])
        self.assertTrue(isinstance(command, CommandNotFound))
        mock_run.assert_not_called()

    @patch('builtins.print')
    def test_pwd_command(self, mock_print):
        command = self.shell._find_command("pwd").make()
        command.execute([])
        mock_print.assert_called_once_with(os.getcwd())

    @patch('os.chdir')
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=True)
    def test_cd_command(self, mock_isdir, mock_exists, mock_chdir):
        command = self.shell._find_command("cd").make()
        command.execute(["/mock/new_dir"])
        mock_chdir.assert_called_once_with("/mock/new_dir")

    @patch('os.chdir')
    @patch('os.getcwd', side_effect=["/mock/old_dir", "/mock/new_dir"])
    def test_cd_command_with_dash(self, mock_getcwd, mock_chdir):
        self.shell._last_dir = "/mock/old_dir"
        command = self.shell._find_command("cd").make()
        command.execute(["-"])
        mock_chdir.assert_called_once_with("/mock/old_dir")

    @patch('os.path.isdir', return_value=False)
    @patch('os.path.exists', return_value=True)
    def test_cd_command_not_a_directory(self, mock_exists, mock_isdir):
        command = self.shell._find_command("cd").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["/mock/file"])
        self.assertEqual(str(context.exception), "/mock/file: Not a directory")

    @patch('os.path.exists', return_value=False)
    def test_cd_command_no_such_file_or_directory(self, mock_exists):
        command = self.shell._find_command("cd").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["/mock/nonexistent"])
        self.assertEqual(str(context.exception), "/mock/nonexistent: No such file or directory")

    @patch('os.path.expanduser', return_value="/mock/home")
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=True)
    @patch('os.chdir')
    def test_cd_command_home_directory(self, mock_chdir, mock_isdir, mock_exists, mock_expanduser):
        command = self.shell._find_command("cd").make()
        command.execute([])
        mock_expanduser.assert_called_once_with("~")
        mock_chdir.assert_called_once_with("/mock/home")


    @patch.dict('os.environ', {'PATH': ''}, clear=True)
    def test_handle_tab_completion_builtin_commands(self):
        # Simulate tab completion for an empty input
        result = []
        for state in range(10):  # Arbitrary large number to exhaust suggestions
            suggestion = self.shell._handle_tab_completion("e", state)
            if suggestion is None:
                break
            result.append(suggestion)

        expected = [cmd for cmd in self.shell.builtin_commands_factory.keys() if cmd.startswith("e")]
        self.assertEqual(sorted(result), sorted(expected))

    @patch.dict('os.environ', {'PATH': '/mock/bin'}, clear=True)
    @patch('os.listdir', side_effect=lambda path: {'/mock/bin': ['cmd1', 'cmd2']}.get(path, []))
    @patch('os.path.isdir', side_effect=lambda path: path in ['/mock/bin'])
    @patch('os.path.isfile', side_effect=lambda path: path in ['/mock/bin/cmd1', '/mock/bin/cmd2'])
    def test_handle_tab_completion_commands_and_path(self, mock_isfile, mock_isdir, mock_listdir):
        # Simulate tab completion for an empty input
        result = []
        for state in range(10):  # Arbitrary large number to exhaust suggestions
            suggestion = self.shell._handle_tab_completion("c", state)
            if suggestion is None:
                break
            result.append(suggestion)

        expected_builtin = [cmd for cmd in self.shell.builtin_commands_factory.keys() if cmd.startswith("c")]
        expected = ['cmd1', 'cmd2'] + expected_builtin
        self.assertEqual(sorted(result), sorted(expected))

    
    @patch.dict('os.environ', {'PATH': ''}, clear=True)
    @patch('os.listdir', side_effect=lambda path: ["file1", "file2", "cmd1"])
    @patch('os.getcwd', side_effect=lambda: "mock")
    def test_handle_tab_completion_commands_and_files(self, mock_getcwd, mock_listdir):
        # Simulate tab completion for an empty input
        result = []
        for state in range(10):  # Arbitrary large number to exhaust suggestions
            suggestion = self.shell._handle_tab_completion("f", state)
            if suggestion is None:
                break
            result.append(suggestion)

        expected_builtin = [cmd for cmd in self.shell.builtin_commands_factory.keys() if cmd.startswith("f")]
        expected = ['file1', 'file2'] + expected_builtin
        self.assertEqual(sorted(result), sorted(expected))

if __name__ == "__main__":
    unittest.main()