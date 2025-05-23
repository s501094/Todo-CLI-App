# Todo CLI Application v2.0.0

A powerful, Python‑based command‑line to‑do list with hierarchical subtasks, three‑state statuses (Not Started, Pending, Hold, Done), and colorized output. Data is stored in `~/.todo_data.json` with no external dependencies beyond a few Python packages.

---

## Features

* **Primary tasks** with arbitrary **subtasks** (IDs like `1`, `1-1`, `1-2`, etc.)
* **Statuses**:

  * ✗ Not Started (red)
  * ● Pending / In‑Progress (yellow)
  * ⏸ Hold / Paused (grey)
  * ✓ Done (green)
* **Priority** levels: `critical`, `high`, `medium`, `low`, each colorized
* **Commands**: `add`, `subtask`, `pending`, `hold`, `complete`, `delete`, `edit`, `list`
* **Sorting** of top‑level tasks by `id`, `due`, `assigned`, or `priority`
* **Tab‑completion** via `argcomplete`
* **Auto‑creation** of `~/.todo_data.json` on first run
* **Standalone packaging** with PyInstaller (no Python needed)
* **Built‑in** `--version` flag (`v2.0.0`)

---

## Prerequisites

* Python **3.12** (using your own virtual environment)
* [pip](https://pip.pypa.io/) for installing dependencies

---

## Installation

1. **Clone or download** this repo:

   ```bash
   git clone https://github.com/yourusername/todo-cli.git
   cd todo-cli
   ```

2. **Activate your Python environment**:

   ```bash
   source /home/tellis/.venv/3_12_2/bin/activate
   ```

3. **Install required packages**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Make the script executable** (Unix/macOS/Linux):

   ```bash
   chmod +x todo.py
   ln -s $(pwd)/todo.py /usr/local/bin/todo
   ```

5. **Enable tab‑completion** (optional):

   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   eval "$(register-python-argcomplete todo)"
   ```

---

## Usage

Invoke via `todo ...` (or `python todo.py ...`). All examples assume you have the script on your `PATH` as `todo`.

### Version

```bash
$ todo --version
todo 2.0.0
```

### Add a primary task

```bash
$ todo add "Write report" --due 2025-06-10 --AssignedTo Alice --priority high
Task 1 added.
```

### Add a subtask

```bash
$ todo subtask 1 "Draft outline" --due 2025-06-05 --AssignedTo Bob --priority medium
Subtask 1-1 added under task 1.
```

### Change status

```bash
# Mark subtask in-progress (pending)
todo pending 1-1

# Put task on hold
todo hold 1
```

### Complete

todo complete 1-1  # ✓ on subtask
todo complete 1    # ✓ on primary (only if no subtasks pending)

### Delete

todo delete 1-1   # deletes subtask
todo delete 1     # deletes task + its subtasks

### Edit a task or subtask

```bash
todo edit 1 --description "Finalize report" --due 2025-06-12 --priority critical
```

### List tasks

```bash
todo list                 # show not‑started, pending, on‑hold, sorted by ID
todo list --all           # include done items
todo list --sort due      # sort primaries by due date
todo list --sort priority # sort by priority
```

---

## Packaging as a Standalone Binary

To bundle into a single executable (`dist/todo`):

```bash
pyinstaller \
  --onefile \
  --name todo \
  --clean \
  todo.py
```

After that, copy the binary to your `PATH`:

```bash
sudo cp dist/todo /usr/local/bin/
chmod +x /usr/local/bin/todo
```

No Python interpreter is required on target systems.

---

## Man Page

A `todo.1` man page is included. To install:

```bash
sudo cp man/todo.1 /usr/local/share/man/man1/
sudo mandb
```

Then run:

```bash
man todo
```

---

## File Location

* Data file: `~/.todo_data.json`
* Stores all tasks, subtasks, and statuses in JSON format

---

## License

MIT © Tyler Ellis