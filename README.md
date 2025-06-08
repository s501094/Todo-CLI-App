Todo CLI Application v2.0.6

A Python-based command-line to-do list manager with hierarchical subtasks, status flags, priorities, tags, categories, notes, colorized output—and built-in reminders.
Stores all data in ~/.todo_data.json (no external backend).

Features
	•	Primary tasks with unlimited subtasks (IDs like 1, 1-1, 1-2, etc.)
	•	Statuses
	•	✗ Not Started (red)
	•	● Pending / In-Progress (yellow)
	•	⏸ Hold / Paused (grey)
	•	✓ Done (green)
	•	Priority levels: critical, high, medium, low (colorized)
	•	Notes field for any task/subtask
	•	Tags and Categories for searching/filtering
	•	Batch operations: mark or delete multiple tasks/subtasks in one command
	•	Sorting: by id, due, assigned, or priority
	•	Tab-completion via argcomplete
	•	Auto-creation of ~/.todo_data.json on first run
	•	Built-in reminders: schedule desktop notifications for any task/subtask
	•	Standalone packaging with PyInstaller (no Python needed for end users)
	•	Built-in --version flag

Prerequisites
	•	Python 3.12 (use your own virtual environment)
	•	pip for installing dependencies

Installation
	1.	Clone or download this repo:

git clone https://github.com/s501094/Todo-CLI-App.git
cd Todo-CLI-App


	2.	Activate your Python environment:

source /home/<username>/.venv/3_12_2/bin/activate


	3.	Install required packages:

pip install -r requirements.txt


	4.	Make the script executable (Unix/macOS/Linux):

chmod +x todo.py
ln -s $(pwd)/todo.py /usr/local/bin/todo

Or copy the PyInstaller-built binary to a folder in your PATH.

	5.	Enable tab-completion (optional):

# Add to ~/.bashrc or ~/.zshrc:
eval "$(register-python-argcomplete todo)"



Usage

Invoke via todo … (or python todo.py …). All examples assume you use the todo alias.

Version

todo --version

Add a primary task

todo add "Write report" \
     --due 2025-06-10 \
     --AssignedTo Alice \
     --priority high \
     --notes "Include exec summary" \
     --tags work urgent \
     --categories business

Add a subtask

todo subtask 1 "Draft outline" \
     --due 2025-06-12 \
     --notes "Use Q2 template" \
     --tags outline

Change status

todo pending 1-1     # Mark subtask in-progress (●)
todo hold 1          # Put task on hold (⏸)

Complete tasks (batch)

todo complete 1-1 2 3    # Mark multiple tasks/subtasks done (✓)

Delete tasks/subtasks (batch)

todo delete 9 10 3-2     # Deletes multiple tasks/subtasks

Edit a task or subtask

todo edit 1 \
     --description "Finalize report" \
     --due 2025-06-12 \
     --priority critical \
     --notes "Manager review" \
     --tags urgent review \
     --categories work

List tasks

todo list                # Show active tasks (not done), sorted by ID
todo list --all          # Include completed tasks
todo list --sort due     # Sort by due date
todo list --sort assigned  # Sort by assignee
todo list --sort priority  # Sort by priority
todo list --notes        # Include the Notes column
todo list --tags         # Show all available tags
todo list --categories   # Show all available categories
todo list --tags urgent review   # Filter by tag
todo list --categories work      # Filter by category
todo list --tags --categories    # Show Tags/Categories columns

Reminders

todo remind 3                   # Remind on task 3 at 09:00 on its due date
todo remind 3-1 --before 1      # Remind one day before subtask 3-1 at 09:00
todo remind 5 --at 14:30        # Remind task 5 at 14:30 on its due date
todo remind 7-2 --before 2 --at 08:00  # Two days before at 08:00

Packaging as a Standalone Binary

To bundle into a single executable:

pyinstaller \
  --onefile \
  --name todo \
  --clean \
  todo.py

Copy the resulting dist/todo into your PATH:

sudo cp dist/todo /usr/local/bin/
chmod +x /usr/local/bin/todo

Man Page

A man/todo.1 page is included. To install:

sudo mkdir -p /usr/local/share/man/man1
sudo cp man/todo.1 /usr/local/share/man/man1/
sudo mandb

Then:

man todo

File Location
	•	Data file: ~/.todo_data.json
Stores everything—tasks, subtasks, status, due dates, notes, tags, categories—in plain JSON.

Dependencies
	•	colorama
	•	tabulate
	•	argcomplete

License

Released under the MIT License.

⸻

Contributions welcome!