import unittest
import unittest.mock
import sys

from unittest.mock import patch
from pyShell import PyShell, CommandError, CommandNotFound


class TestPyShell(unittest.TestCase):
    def setUp(self):
        self.shell = PyShell()

    def test_echo_command(self):
        with patch('builtins.print') as mock_print:
            command = self.shell._find_command("echo").make()
            command.execute(["Hello", "World"])
            mock_print.assert_called_once_with("Hello World")

    def test_exit_command(self):
        with patch('sys.exit') as mock_exit:
            command = self.shell._find_command("exit").make()
            command.execute(["0"])
            mock_exit.assert_called_once_with(0)

    def test_exit_command_with_error_code(self):
        with patch('sys.exit') as mock_exit:
            command = self.shell._find_command("exit").make()
            command.execute(["127"])
            mock_exit.assert_called_once_with(127)

    def test_exit_command_without_args(self):
        with patch('sys.exit') as mock_exit:
            command = self.shell._find_command("exit").make()
            command.execute([])
            mock_exit.assert_called_once_with(0)

    def test_exit_command_invalid_argument(self):
        command = self.shell._find_command("exit").make()
        with self.assertRaises(CommandError) as context:
            command.execute(["invalid"])
        self.assertEqual(str(context.exception), "invalid: numeric argument required")

    def test_type_command_builtin(self):
        with patch('builtins.print') as mock_print:
            command = self.shell._find_command("type").make()
            command.execute(["echo"])
            mock_print.assert_called_once_with("echo is a shell builtin")

    def test_type_command_builtin_multile_args(self):
        with patch('builtins.print') as mock_print:
            command = self.shell._find_command("type").make()
            command.execute(["echo", "exit"])
            mock_print.assert_has_calls([
                unittest.mock.call("echo is a shell builtin"),
                unittest.mock.call("exit is a shell builtin")
            ], any_order=False)

            self.assertEqual(mock_print.call_count, 2)

    def test_type_command_not_found(self):
        with patch('builtins.print') as mock_print:
            command = self.shell._find_command("type").make()
            command.execute(["nonexistent"])
            mock_print.assert_called_once_with("nonexistent: not found", file=sys.stderr)

    def test_command_not_found(self):
        with patch('builtins.print') as mock_print:
            command = self.shell._find_command("nonexistent").make()
            command.execute([])
            mock_print.assert_called_once_with("nonexistent: Command not found", file=sys.stderr)

    @patch.dict('os.environ', {'PATH': '/mock/bin/ls'}, clear=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.access', return_value=True)
    def test_executable_command(self, mock_access, mock_isfile):
        with patch('subprocess.run') as mock_run:
            command = self.shell._find_command("ls").make()
            command.execute(["-l"])
            mock_run.assert_called_once_with(["ls", "-l"])

    @patch.dict('os.environ', {'PATH': '/mock/bin/'}, clear=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.access', return_value=True)
    @patch('builtins.print') # Mock print to avoid printing to stdout
    def test_executable_command_not_found(self, mock_print, mock_access, mock_isfile):
        with patch('subprocess.run') as mock_run:
            command = self.shell._find_command("ls").make()
            command.execute(["-l"])
            self.assertTrue(isinstance(command, CommandNotFound))
            mock_run.assert_not_called()

    @patch.dict('os.environ', {'PATH': '/mock/bin/ls'}, clear=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.access', return_value=False)
    @patch('builtins.print') # Mock print to avoid printing to stdout
    def test_executable_command_not_executable_file(self, mock_print, mock_access, mock_isfile):
        with patch('subprocess.run') as mock_run:
            command = self.shell._find_command("ls").make()
            command.execute(["-l"])
            self.assertTrue(isinstance(command, CommandNotFound))
            mock_run.assert_not_called()

if __name__ == "__main__":
    unittest.main()