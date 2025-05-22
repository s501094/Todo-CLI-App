# Todo CLI Application

A simple, cross-platform command-line to-do list application written in Python. It supports colored output, filtering, sorting, editing, and more, all stored in a local JSON file.

---

## Features

* **Add tasks** with description, due date, assignee, and priority
* **List tasks** in a neat, colorized table
* **Filter tasks** by completion status, keyword, or date ranges
* **Sort tasks** by ID, due date, assignee, or priority
* **Edit tasks**: update description, due date, assignee, or priority
* **Complete & delete tasks** with simple commands
* **Date filters**: `--due-before`, `--due-after`, `--due-today`, `--due-week`, `--due-month`
* **Tab-completion** for commands and flags via `argcomplete`
* **Portable**: runs on any system with Python 3.12+, no external database
* **Standalone packaging**: optionally bundle into a single executable with PyInstaller

---

## Prerequisites

* Python **3.12** or later
* [pip](https://pip.pypa.io/) to install dependencies

---

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/todo-cli.git
   cd todo-cli
   ```

2. **Create a virtual environment** (optional, but recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .\.venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Make the script executable** (Unix/macOS):

   ```bash
   chmod +x todo.py
   ln -s $(pwd)/todo.py /usr/local/bin/todo
   ```

5. **Enable tab-completion** (optional):

   * **Bash** (`~/.bashrc`):

     ```bash
     eval "$(register-python-argcomplete todo)"
     ```
   * **Zsh** (`~/.zshrc`):

     ```zsh
     autoload -U +X compinit; compinit
     autoload -U +X bashcompinit; bashcompinit
     eval "$(register-python-argcomplete todo)"
     ```

---

## Usage

All commands are invoked via the `todo` executable or `python todo.py`.

### Add a task

```bash
todo add "Buy groceries" --due 2025-06-01 --AssignedTo "Alice" --priority high
```

* **description**: task text (required)
* `--due YYYY-MM-DD`: due date (defaults to 1 week from today)
* `--AssignedTo NAME`: name of the person assigned
* `--priority [critical|high|medium|low]`: task priority

### List tasks

```bash
todo list
```

Defaults to pending tasks sorted by due date.

#### Options

* `--all`: include completed tasks
* `--sort [due|assigned|priority|id]`: sort field
* `--filter KEYWORD`: search in descriptions
* Date filters (only pending, unless `--all`):

  * `--due-before YYYY-MM-DD`
  * `--due-after YYYY-MM-DD`
  * `--due-today`
  * `--due-week`
  * `--due-month`

### Complete a task

```bash
todo complete 3
```

Mark task ID 3 as done.

### Delete a task

```bash
todo delete 2
```

Delete task ID 2.

### Edit a task

```bash
todo edit 5 --description "Write tests" --due 2025-06-10 --priority medium
```

Update any subset of fields for task ID 5.

---

## Packaging

To create a standalone executable (no Python required) with [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --name todo --add-data \
  "$PWD/.todo_data.json:todo_data.json" \
  todo.py
```

This outputs `dist/todo` (or `dist/todo.exe` on Windows).

---

## Configuration

* The data file is stored at `~/.todo_data.json`.
* On first run, an empty list is created automatically.
* When bundled, a default template can be copied into place.

---

## License

MIT © Tyler Ellis

