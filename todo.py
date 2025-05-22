#!/home/tellis/.venv/3_12_2/bin/python3

import argparse
import json
import os
import sys
import shutil
import textwrap
import argcomplete # type: ignore
from datetime import datetime, date, timedelta
from tabulate import tabulate # type: ignore
from colorama import Fore, Style, init

init(autoreset=True)


def get_data_file_path():
    """
    Return the path to ~/.todo_data.json, copying the
    bundled template on first run (when frozen), or
    creating an empty list file if none exists.
    """
    user_path = os.path.expanduser("~/.todo_data.json")

    # If running in a PyInstaller bundle, copy the bundled template out
    if getattr(sys, "frozen", False):
        bundle_dir   = sys._MEIPASS
        bundled_name = ".todo_data.json"
        bundled_path = os.path.join(bundle_dir, bundled_name)

        if not os.path.exists(user_path) and os.path.exists(bundled_path):
            try:
                shutil.copyfile(bundled_path, user_path)
            except Exception as e:
                print(f"Error copying bundled data file: {e}")
                sys.exit(1)

    # Ensure the user file exists (empty list if first run)
    if not os.path.exists(user_path):
        try:
            with open(user_path, "w") as f:
                json.dump([], f)
        except PermissionError:
            print("Unable to create data file at "
                  f"{user_path}. Check permissions.")
            sys.exit(1)

    return user_path


def load_tasks():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        tasks = json.load(f)

    for t in tasks:
        d = t.get("due")
        if isinstance(d, str):
            for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                try:
                    t["due"] = datetime.strptime(d, fmt).date()
                    break
                except ValueError:
                    continue
    return tasks


def save_tasks(tasks):
    """Save tasks to JSON, converting date objects to ISO strings."""
    out = []
    for t in tasks:
        copy = t.copy()
        d = copy.get("due")
        if isinstance(d, date):
            copy["due"] = d.isoformat()
        out.append(copy)
    with open(DATA_FILE, "w") as f:
        json.dump(out, f, indent=2)


def list_tasks(args):
    tasks       = load_tasks()
    default_due = date.today() + timedelta(days=7)

    # apply date-based filters (due_before, due_after, etc) as before...
    if getattr(args, "due_before", None):
        tasks = [t for t in tasks if (t.get("due") or default_due) <= args.due_before]
    if getattr(args, "due_after", None):
        tasks = [t for t in tasks if (t.get("due") or default_due) >= args.due_after]
    if getattr(args, "due_today", False):
        today = date.today()
        tasks = [t for t in tasks if (t.get("due") or default_due) == today]
    if getattr(args, "due_week", False):
        start = date.today()
        end   = start + timedelta(days=7)
        tasks = [t for t in tasks if start <= (t.get("due") or default_due) < end]
    if getattr(args, "due_month", False):
        start = date.today()
        end   = start + timedelta(days=30)
        tasks = [t for t in tasks if start <= (t.get("due") or default_due) < end]

    # Prepare wrapping parameters
    term_width = shutil.get_terminal_size().columns
    # estimate the width consumed by the other columns + padding/borders:
    reserved = sum([4,   # ID
                    3,   # Status
                    10,  # Due Date
                    15,  # AssignedTo
                    8,   # Priority
                    20]) # grid lines & padding
    desc_width = max(10, term_width - reserved)

    rows = []
    for t in tasks:
        if not args.all and t.get("done", False):
            continue

        # base data
        task_id  = t["id"]
        done     = t.get("done", False)
        status   = ("✓" if done else "✗")
        due_date = t.get("due") or default_due
        assigned = t.get("AssignedTo", "Ty Ellis")
        prio     = t.get("priority", "low")

        # wrap and color description
        raw_desc = t["description"]
        wrapped  = textwrap.wrap(raw_desc, desc_width) or [""]
        joined   = "\n".join(wrapped)
        if done:
            desc_cell = Fore.GREEN + joined + Style.RESET_ALL
            status_cell = Fore.GREEN + status + Style.RESET_ALL
        else:
            desc_cell = Fore.RED + joined + Style.RESET_ALL
            status_cell = Fore.RED + status + Style.RESET_ALL

        # color priority
        if prio == "critical":
            prio_disp = Fore.MAGENTA + prio
        elif prio == "high":
            prio_disp = Fore.YELLOW + prio
        elif prio == "medium":
            prio_disp = Fore.CYAN + prio
        else:
            prio_disp = Fore.BLUE + prio
        prio_cell = prio_disp + Style.RESET_ALL

        rows.append([
            task_id,
            desc_cell,
            status_cell,
            due_date,
            assigned,
            prio_cell
        ])

    if not rows:
        print("No tasks to show.")
        return

    # sorting
    if args.sort == "due":
        rows.sort(key=lambda r: r[3])
    elif args.sort == "assigned":
        rows.sort(key=lambda r: r[4].lower())
    elif args.sort == "priority":
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        rows.sort(key=lambda r: order.get(r[5].strip(Style.RESET_ALL).lower(), 99))
    elif args.sort == "id":
        rows.sort(key=lambda r: r[0])

    # description keyword filter
    if getattr(args, "filter", None):
        rows = [r for r in rows if args.filter.lower() in r[1].lower()]
        if not rows:
            print("No tasks match filter.")
            return

    # final print
    print(tabulate(
        rows,
        headers=["ID", "Description", "Status", "Due Date", "AssignedTo", "Priority"],
        colalign=("center", "left", "center", "center", "left", "center"),
        stralign="left",
        tablefmt="fancy_grid"
    ))


def add_task(args):
    tasks    = load_tasks()
    task_id  = len(tasks) + 1
    due_date = args.due or (date.today() + timedelta(days=7))
    assigned = args.AssignedTo or "Ty Ellis"
    prio     = args.priority or "low"

    tasks.append({
        "id":          task_id,
        "description": args.description,
        "done":        False,
        "due":         due_date,
        "AssignedTo":  assigned,
        "priority":    prio
    })
    save_tasks(tasks)
    print(f"Task {task_id} added.")


def complete_task(args):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == args.task_id:
            t["done"] = True
            save_tasks(tasks)
            print(f"Task {args.task_id} marked as complete.")
            return
    print(f"Task {args.task_id} not found.")


def delete_task(args):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == args.task_id:
            tasks.remove(t)
            save_tasks(tasks)
            print(f"Task {args.task_id} deleted.")
            return
    print(f"Task {args.task_id} not found.")


def edit_task(args):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == args.task_id:
            if args.description:
                t["description"] = args.description
            if args.due:
                t["due"] = args.due
            if args.AssignedTo:
                t["AssignedTo"] = args.AssignedTo
            if args.priority:
                t["priority"] = args.priority
            save_tasks(tasks)
            print(f"Task {args.task_id} updated.")
            return
    print(f"Task {args.task_id} not found.")


def main():
    global DATA_FILE
    DATA_FILE = get_data_file_path()

    parser = argparse.ArgumentParser(prog="todo", description="Personal CLI To-Do App")
    subs   = parser.add_subparsers(dest="command", required=True)

    # central command definitions
    commands = {
        "list": {
            "func": list_tasks,
            "help": "List tasks",
            "args": [
                (["--all"],        {"action":"store_true", "help":"Include completed tasks"}),
                (["--sort"],       {"choices":["due","assigned","priority","id"], "default":"due",
                                    "help":"Sort by id, due date, priority, or assigned"}),
                (["--due-before"], {"type": date.fromisoformat,
                                    "help":"Show tasks due before this date (YYYY-MM-DD)"}),
                (["--due-after"],  {"type": date.fromisoformat,
                                    "help":"Show tasks due after this date (YYYY-MM-DD)"}),
                (["--due-today"],  {"action":"store_true", "help":"Show tasks due today"}),
                (["--due-week"],   {"action":"store_true", "help":"Show tasks due this week"}),
                (["--due-month"],  {"action":"store_true", "help":"Show tasks due this month"}),
                (["--filter"],     {"help":"Filter by keyword in description"})
            ]
        },
        "add": {
            "func": add_task,
            "help": "Add a new task",
            "args": [
                (["description"], {"help":"Task description"}),
                (["--due"],       {"type": date.fromisoformat,
                                   "help":"Due date (YYYY-MM-DD)"}),
                (["--AssignedTo"],{"help":"Developer assigned to task"}),
                (["--priority"],  {"choices":["critical","high","medium","low"],
                                   "help":"Task priority"})
            ]
        },
        "complete": {
            "func": complete_task,
            "help": "Mark a task complete",
            "args": [
                (["task_id"], {"type":int, "help":"ID to mark complete"})
            ]
        },
        "delete": {
            "func": delete_task,
            "help": "Delete a task",
            "args": [
                (["task_id"], {"type":int, "help":"ID to delete"})
            ]
        },
        "edit": {
            "func": edit_task,
            "help": "Edit a task",
            "args": [
                (["task_id"],       {"type":int, "help":"ID to edit"}),
                (["--description"], {"help":"New description"}),
                (["--due"],         {"type": date.fromisoformat,
                                     "help":"New due date (YYYY-MM-DD)"}),
                (["--AssignedTo"],  {"help":"New developer assigned"}),
                (["--priority"],    {"choices":["critical","high","medium","low"],
                                     "help":"New task priority"})
            ]
        }
    }

    # build parsers & dispatch
    for cmd, opts in commands.items():
        sp = subs.add_parser(cmd, help=opts["help"])
        for flags, params in opts["args"]:
            sp.add_argument(*flags, **params)
        sp.set_defaults(func=opts["func"])

    # enable tab-completion
    argcomplete.autocomplete(parser)

    # parse args & run
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
