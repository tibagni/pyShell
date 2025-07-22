[![Python application](https://github.com/tibagni/pyShell/actions/workflows/python-app.yml/badge.svg)](https://github.com/tibagni/pyShell/actions/workflows/python-app.yml)

# pyShell

A custom shell built from scratch in Python. This project was a fun exploration into how shells work, implementing core functionalities like command parsing, I/O redirection, and process pipelines.

As a unique feature, it also integrates with AI to offer command generation, explanation, and summarization of files and directories.

> **Note:** This is a personal project with a limited feature set. It's shared in the hope that it might serve as a useful or interesting starting point for others looking to build their own command-line tools.

---

## Features

### Core Shell Functionality

*   **Command Execution**: Runs built-in commands (`echo`, `exit`, `cd`, `pwd`, `type`, `history`) and any external command available in the system's `$PATH`.
*   **Pipelines**: Chain multiple commands together using the pipe (`|`) operator.
*   **I/O Redirection**: Redirect `stdout` (`>`, `>>`) and `stderr` (`2>`) to files.
*   **Advanced Input Parsing**: Handles single and double quotes, character escaping (`\`), and environment variable expansion (`$VAR`).
*   **Tab Completion**: Context-aware completion for commands and file paths.
*   **Persistent History**: Saves command history between sessions (requires `HISTFILE` to be set).

### AI-Powered Features

*   **`do`**: Describe a task in plain English, and have the AI generate the shell command for you. Includes a safety check for potentially risky commands.
*   **`explain`**: Get a simple, human-readable explanation of what any shell command does.
*   **`summarize`**: Summarize the purpose or content of a file or directory using AI. Works for code, markdown, text files, or entire directories.
*   **`quickref`**: Get a summarized, beginner-friendly guide for any Unix command

---

## How to Run

A wrapper script `run.sh` is provided to easily run the shell or its tests within the virtual environment.

### Launch the Shell

To start an interactive `pyShell` session, simply execute:

```bash
./run.sh
```

### Run Tests

To run the suite of unit tests for the project, use the -t flag:

```bash
./run.sh -t
```
---

## Usage

Once inside `pyShell`, you can use it like a standard Unix shell.

### Standard Commands

```console
$ echo "Hello from pyShell!"
Hello from pyShell!

$ ls -l | wc -l > line_count.txt

$ cd /tmp

$ pwd
/tmp
```

## AI Commands

The first time you use an AI-powered command (`do`, `explain`, `summarize`), pyShell will prompt you to configure your AI provider settings. These settings are saved to a .pyShell file in your home directory (`~/.pyShell`) for future sessions.

### Example: `do` command

Let the AI figure out the command for you.

```console
$ do find all files in the current directory that have been modified in the last 24 hours
./pyShell.py
./README.md
```

### Example: `explain` command

Understand what a complex command does before you run it.

```console
$ explain "tar -czvf archive.tar.gz /path/to/directory"
This command creates a compressed archive.
- 'c': Creates a new .tar archive.
- 'z': Compresses the archive with gzip.
- 'v': Verbosely shows the .tar file progress.
- 'f': Specifies the archive file name.
Example: Backing up a project folder.
```

### Example: `summarize` command

Summarize the contents or purpose of a file or directory.

```console
$ summarize script.py
This Python script reads a CSV file and prints summary statistics for each column.

$ summarize my_folder/
This folder contains several Python scripts for data analysis, including data_clean.py (cleans input data) and plot_results.py (generates graphs).
```

### Example: `quickref` command

Get a quick, summarized reference for any Unix command, including its purpose, main options, and usage examples.

```console
$ quickref tar
 Fetching the man pages for man... 
 Summarizing content... 
Summary:
  tar is an archiving utility for combining and extracting files.
Common Options:
  -c   Create a new archive
  -x   Extract files from an archive
  -v   Verbose output
  -f   Specify archive file name
Examples:
  tar -cvf archive.tar folder/
  tar -xvf archive.tar
```
