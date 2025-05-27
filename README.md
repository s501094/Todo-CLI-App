# Todo CLI Application v2.0.6

A Python-based command-line to-do list manager with hierarchical subtasks, status flags, priorities, tags, categories, notes, and colorized output.
Stores all data in `~/.todo_data.json` (no external backend).

## Features

* **Primary tasks** with unlimited **subtasks** (IDs like `1`, `1-1`, `1-2`, etc.)
* **Statuses**:

  * ✗ Not Started (red)
  * ● Pending / In-Progress (yellow)
  * ⏸ Hold / Paused (grey)
  * ✓ Done (green)
* **Priority** levels: `critical`, `high`, `medium`, `low` (colorized)
* **Notes** field for any task/subtask
* **Tags** and **categories** for searching/filtering
* **Batch operations:** mark or delete multiple tasks/subtasks in one command
* **Sorting:** by `id`, `due`, `assigned`, or `priority`
* **Tab-completion** via `argcomplete`
* **Auto-creation** of `~/.todo_data.json` on first run
* **Standalone packaging** with PyInstaller (no Python needed for end users)
* **Built-in** `--version` flag

## Prerequisites

* Python 3.12 (run in your own virtual environment)
* [pip](https://pip.pypa.io/) for installing dependencies

## Installation

1. Clone or download this repo:

   ```bash
   git clone https://github.com/s501094/Todo-CLI-App.git
   cd todo-cli
   ```

2. Activate your Python environment:

   ```bash
   source /home/<homeDir>/.venv/3_12_2/bin/activate
   ```

3. Install required packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Make the script executable (Unix/macOS/Linux):

   ```bash
   chmod +x todo.py
   ln -s $(pwd)/todo.py /usr/local/bin/todo
   ```
   or copy the dist/Linux/todo into a folder already in your $PATH variable.
   
5. Enable tab-completion (optional):

   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   eval "$(register-python-argcomplete todo)"
   ```

## Usage

Invoke via `todo ...` (or `python todo.py ...`).
All examples assume you have the script aliased as `todo`.

### Version

```bash
todo --version
```

### Add a primary task

```bash
todo add "Write report" --due 2025-06-10 --AssignedTo Alice --priority high --notes "Include exec summary" --tags work urgent --categories business
```

### Add a subtask

```bash
todo subtask 1 "Draft outline" --due 2025-06-12 --notes "Use Q2 template" --tags outline
```

### Change status

```bash
todo pending 1-1         # Mark subtask in-progress (pending)
todo hold 1              # Put task on hold
```

### Complete tasks (batch)

```bash
todo complete 1-1 2 3    # Mark multiple tasks or subtasks complete
```

### Delete tasks/subtasks (batch)

```bash
todo delete 9 10 3-2     # Deletes multiple tasks and/or subtasks
```

### Edit a task or subtask

```bash
todo edit 1 --description "Finalize report" --due 2025-06-12 --priority critical --notes "Manager review" --tags urgent review --categories work
```

### List tasks

```bash
todo list                    # Show active tasks (not done), sorted by ID
todo list --all              # Include completed tasks
todo list --sort due         # Sort by due date
todo list --sort assigned    # Sort by assignee
todo list --sort priority    # Sort by priority
```

### Tags & Categories

```bash
todo list --tags                 # Show all recognized tags
todo list --categories           # Show all recognized categories
todo list --tags urgent work     # Filter and show only tasks with specified tags
todo list --categories work      # Filter and show only tasks in specified categories
todo list --tags --categories    # Show columns for tags/categories in output
```

### Show notes in output

```bash
todo list --notes
```

## Packaging as a Standalone Binary

To bundle into a single executable (`dist/todo`):

```bash
pyinstaller \
  --onefile \
  --name todo \
  --clean \
  todo.py
```

Copy the binary to your `PATH`:

```bash
sudo cp dist/todo /usr/local/bin/
chmod +x /usr/local/bin/todo
```

## Man Page

A `todo.1` man page is included. To install:

```bash
sudo mkdir /usr/local/share/man/man1
sudo cp man/todo.1 /usr/local/share/man/man1/
sudo mandb
```

Then run:

```bash
man todo
```

## File Location

* Data file: `~/.todo_data.json`
* Stores all tasks, subtasks, status, tags, categories, and notes in plain JSON format.

## Dependencies

* [colorama](https://pypi.org/project/colorama/)
* [tabulate](https://pypi.org/project/tabulate/)
* [argcomplete](https://pypi.org/project/argcomplete/)

## License

MIT License

---

**Contributions welcome!**
