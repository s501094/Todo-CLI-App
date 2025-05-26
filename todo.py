#!/home/tellis/.venv/3_12_2/bin/python3
VERSION = "1.0.6"

import argparse
import json
import os
import sys
import shutil
import textwrap
import argcomplete  # type: ignore
from argparse import RawDescriptionHelpFormatter
from datetime import datetime, date, timedelta
from tabulate import tabulate  # type: ignore
from colorama import Fore, Style, init

# ─── Preserve ANSI color codes through Tabulate ────────────────────────────
init(autoreset=True, strip=False)
# ────────────────────────────────────────────────────────────────────────────

DATE_FMT    = "%Y-%m-%d"
default_due = (date.today() + timedelta(days=4)).isoformat()

EXAMPLES = r"""
Examples:
  # Show version
  todo --version

  # Add a primary task (defaults due in 4 days)
  todo add "Write report" --AssignedTo Alice --priority high --notes "Include executive summary"

  # Add a subtask under task 1
  todo subtask 1 "Draft outline" --due 2025-06-05 --notes "Use old template"

  # Change status
  todo pending 1-1   # in-progress (yellow ●)
  todo hold 1       # on-hold (grey ⏸)

  # Complete tasks
  todo complete 1-1
  todo complete 1    # only if no subtasks pending

  # Delete
  todo delete 1-1
  todo delete 1

  # Edit notes or any field
  todo edit 1 --notes "Notify team on Slack"

  # List
  todo list              # show active tasks
  todo list --all        # include done
  todo list --sort due   # sort by due date
"""

def get_data_file_path():
    """Ensure ~/.todo_data.json exists (copy bundled if frozen)."""
    user_path = os.path.expanduser("~/.todo_data.json")
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, ".todo_data.json")
        if os.path.exists(bundled) and not os.path.exists(user_path):
            shutil.copyfile(bundled, user_path)
    if not os.path.exists(user_path):
        with open(user_path, "w") as f:
            json.dump([], f)
    return user_path

DATA_FILE = get_data_file_path()

def load_tasks():
    """Load and normalize tasks, recovering from JSON errors."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE) as f:
            tasks = json.load(f)
    except json.JSONDecodeError:
        bak = DATA_FILE + ".bak"
        shutil.copyfile(DATA_FILE, bak)
        tasks = []
        with open(DATA_FILE, "w") as f:
            json.dump([], f)
    for t in tasks:
        t.setdefault("subtasks", [])
        t.setdefault("pending", False)
        t.setdefault("hold", False)
        t.setdefault("notes", "")
    return tasks

def save_tasks(tasks):
    """Persist tasks back to JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def list_tasks(args):
    tasks = load_tasks()
    # Compute column widths
    term_w     = shutil.get_terminal_size().columns
    reserved   = 4 + 3 + 10 + 15 + 8 + 20
    avail      = max(20, term_w - reserved)
    desc_w     = max(10, int(avail * 0.6))
    notes_w    = max(10, avail - desc_w)

    # Sorting key for primaries
    def primary_key(t):
        if args.sort == "due":
            ds = t.get("due") or default_due
            try:
                return datetime.strptime(ds, DATE_FMT)
            except ValueError:
                return datetime.today()
        if args.sort == "assigned":
            return t.get("AssignedTo","").lower()
        if args.sort == "priority":
            order = {"critical":0,"high":1,"medium":2,"low":3}
            return order.get(t.get("priority","low").lower(), 99)
        return t["id"]

    primaries = sorted(tasks, key=primary_key)
    rows = []

    for t in primaries:
        if not args.all and t.get("done"):
            continue

        tid      = str(t["id"])
        due_date = t.get("due") or default_due
        assigned = t.get("AssignedTo","Tyler Ellis")
        prio     = t.get("priority","low").lower()
        notes    = t.get("notes","")

        # Wrap & color description
        desc_lines = textwrap.wrap(t["description"], desc_w) or [""]
        if t.get("done"):
            status_col = Fore.GREEN + "✓" + Style.RESET_ALL
            desc_col   = "\n".join(Fore.GREEN + ln + Style.RESET_ALL for ln in desc_lines)
        elif t.get("hold"):
            status_col = Fore.LIGHTBLACK_EX + "⏸" + Style.RESET_ALL
            desc_col   = "\n".join(Fore.LIGHTBLACK_EX + ln + Style.RESET_ALL for ln in desc_lines)
        elif t.get("pending"):
            status_col = Fore.YELLOW + "●" + Style.RESET_ALL
            desc_col   = "\n".join(Fore.YELLOW + ln + Style.RESET_ALL for ln in desc_lines)
        else:
            status_col = Fore.RED + "✗" + Style.RESET_ALL
            desc_col   = "\n".join(Fore.RED + ln + Style.RESET_ALL for ln in desc_lines)

        # Wrap notes (plain text)
        notes_lines = textwrap.wrap(notes, notes_w) or [""]
        notes_col   = "\n".join(notes_lines)

        # Color priority
        if prio == "critical":
            prio_col = Fore.MAGENTA + prio + Style.RESET_ALL
        elif prio == "high":
            prio_col = Fore.YELLOW + prio + Style.RESET_ALL
        elif prio == "medium":
            prio_col = Fore.CYAN + prio + Style.RESET_ALL
        else:
            prio_col = Fore.BLUE + prio + Style.RESET_ALL

        rows.append([tid, desc_col, status_col, due_date, assigned, prio_col, notes_col])

        # Subtasks, anchored & indented
        for sub in sorted(t["subtasks"], key=lambda s: int(s["id"].split("-",1)[1])):
            if not args.all and sub.get("done"):
                continue
            sub_lines = textwrap.wrap(sub["description"], desc_w) or [""]
            if sub.get("done"):
                s_sym  = Fore.GREEN + "✓" + Style.RESET_ALL
                s_desc = "\n".join(Fore.GREEN + ln + Style.RESET_ALL for ln in sub_lines)
            elif sub.get("hold"):
                s_sym  = Fore.LIGHTBLACK_EX + "⏸" + Style.RESET_ALL
                s_desc = "\n".join(Fore.LIGHTBLACK_EX + ln + Style.RESET_ALL for ln in sub_lines)
            elif sub.get("pending"):
                s_sym  = Fore.YELLOW + "●" + Style.RESET_ALL
                s_desc = "\n".join(Fore.YELLOW + ln + Style.RESET_ALL for ln in sub_lines)
            else:
                s_sym  = Fore.RED + "✗" + Style.RESET_ALL
                s_desc = "\n".join(Fore.RED + ln + Style.RESET_ALL for ln in sub_lines)

            sprio = sub.get("priority","low").lower()
            if sprio == "critical":
                sp = Fore.MAGENTA + sprio + Style.RESET_ALL
            elif sprio == "high":
                sp = Fore.YELLOW + sprio + Style.RESET_ALL
            elif sprio == "medium":
                sp = Fore.CYAN + sprio + Style.RESET_ALL
            else:
                sp = Fore.BLUE + sprio + Style.RESET_ALL

            rows.append([
                "",
                "├─ " + s_desc,
                s_sym,
                sub.get("due",""),
                sub.get("AssignedTo","Tyler Ellis"),
                sp,
                ""  # subtasks have no notes
            ])

    if not rows:
        print("No tasks to show.")
        return

    print(tabulate(
        rows,
        headers=["ID","Description","Status","Due Date","AssignedTo","Priority","Notes"],
        colalign=("center","left","center","center","left","center","left"),
        stralign="left",
        tablefmt="fancy_grid"
    ))

def add_task(args):
    tasks = load_tasks()
    nid   = len(tasks) + 1
    tasks.append({
        "id":         nid,
        "description": args.description,
        "done":        False,
        "pending":     False,
        "hold":        False,
        "due":         args.due or default_due,
        "AssignedTo":  args.AssignedTo or "Tyler Ellis",
        "priority":    args.priority or "low",
        "notes":       args.notes or "",
        "subtasks":    []
    })
    save_tasks(tasks)
    print(f"Task {nid} added.")

def add_subtask(args):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == args.parent_id:
            idx  = len(t["subtasks"]) + 1
            sid  = f"{t['id']}-{idx}"
            t["subtasks"].append({
                "id":          sid,
                "description": args.description,
                "done":        False,
                "pending":     False,
                "hold":        False,
                "due":         args.due or default_due,
                "AssignedTo":  args.AssignedTo or "Tyler Ellis",
                "priority":    args.priority or "low",
                "notes":       args.notes or ""
            })
            save_tasks(tasks)
            print(f"Subtask {sid} added under task {t['id']}.")
            return
    print(f"Parent task {args.parent_id} not found.")

def pending_task(args):
    tid   = args.task_id
    tasks = load_tasks()
    if "-" in tid:
        pid,_ = tid.split("-",1)
        for t in tasks:
            if str(t["id"]) == pid:
                for sub in t["subtasks"]:
                    if sub["id"] == tid:
                        sub["pending"] = True
                        sub["done"]    = False
                        sub["hold"]    = False
                        save_tasks(tasks)
                        print(f"Subtask {tid} marked pending.")
                        return
        print(f"Subtask {tid} not found.")
        return
    for t in tasks:
        if str(t["id"]) == tid:
            t["pending"] = True
            t["done"]    = False
            t["hold"]    = False
            save_tasks(tasks)
            print(f"Task {tid} marked pending.")
            return
    print(f"Task {tid} not found.")

def hold_task(args):
    tid   = args.task_id
    tasks = load_tasks()
    if "-" in tid:
        pid,_ = tid.split("-",1)
        for t in tasks:
            if str(t["id"]) == pid:
                for sub in t["subtasks"]:
                    if sub["id"] == tid:
                        sub["hold"]    = True
                        sub["done"]    = False
                        sub["pending"] = False
                        save_tasks(tasks)
                        print(f"Subtask {tid} marked on-hold.")
                        return
        print(f"Subtask {tid} not found.")
        return
    for t in tasks:
        if str(t["id"]) == tid:
            t["hold"]    = True
            t["done"]    = False
            t["pending"] = False
            save_tasks(tasks)
            print(f"Task {tid} marked on-hold.")
            return
    print(f"Task {tid} not found.")

def complete_task(args):
    tid   = args.task_id
    tasks = load_tasks()
    if "-" in tid:
        pid,_ = tid.split("-",1)
        for t in tasks:
            if str(t["id"]) == pid:
                for sub in t["subtasks"]:
                    if sub["id"] == tid:
                        sub["done"]    = True
                        sub["pending"] = False
                        sub["hold"]    = False
                        save_tasks(tasks)
                        print(f"Subtask {tid} marked complete.")
                        return
        print(f"Subtask {tid} not found.")
        return
    for t in tasks:
        if str(t["id"]) == tid:
            pending = [s for s in t["subtasks"] if not s.get("done")]
            if pending:
                print(f"Cannot complete task {tid}: {len(pending)} subtasks still pending.")
                return
            t["done"]    = True
            t["pending"] = False
            t["hold"]    = False
            save_tasks(tasks)
            print(f"Task {tid} marked complete.")
            return
    print(f"Task {tid} not found.")

def delete_task(args):
    tid   = args.task_id
    tasks = load_tasks()
    if "-" in tid:
        pid,_ = tid.split("-",1)
        for t in tasks:
            if str(t["id"]) == pid:
                before = len(t["subtasks"])
                t["subtasks"] = [s for s in t["subtasks"] if s["id"] != tid]
                if len(t["subtasks"]) < before:
                    save_tasks(tasks)
                    print(f"Subtask {tid} deleted.")
                    return
        print(f"Subtask {tid} not found.")
        return
    new = [t for t in tasks if str(t["id"]) != tid]
    if len(new) < len(tasks):
        save_tasks(new)
        print(f"Task {tid} deleted (and its subtasks).")
    else:
        print(f"Task {tid} not found.")

def edit_task(args):
    tid   = str(args.task_id)
    tasks = load_tasks()
    for t in tasks:
        if str(t["id"]) == tid:
            if args.description: t["description"] = args.description
            if args.due:         t["due"]         = args.due
            if args.AssignedTo:  t["AssignedTo"]  = args.AssignedTo
            if args.priority:    t["priority"]    = args.priority
            if args.notes is not None:
                t["notes"] = args.notes
            save_tasks(tasks)
            print(f"Task {tid} updated.")
            return
        for sub in t["subtasks"]:
            if sub["id"] == tid:
                if args.description: sub["description"] = args.description
                if args.due:         sub["due"]         = args.due
                if args.AssignedTo:  sub["AssignedTo"]  = args.AssignedTo
                if args.priority:    sub["priority"]    = args.priority
                if args.notes is not None:
                    sub["notes"] = args.notes
                save_tasks(tasks)
                print(f"Subtask {tid} updated.")
                return
    print(f"Task or subtask {tid} not found.")

def main():
    parser = argparse.ArgumentParser(
        prog="todo",
        description="Personal CLI To-Do App with hierarchical subtasks, notes, and three-state status",
        epilog=EXAMPLES,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}",
                        help="Show program version and exit")

    subs = parser.add_subparsers(dest="command", required=True)

    lst = subs.add_parser("list", help="List tasks & subtasks", formatter_class=RawDescriptionHelpFormatter)
    lst.add_argument("--all", action="store_true", help="Include completed")
    lst.add_argument("--sort", choices=["due","assigned","priority","id"], default="id",
                     help="Sort primaries by this field")
    lst.set_defaults(func=list_tasks)

    add = subs.add_parser("add", help="Add a primary task")
    add.add_argument("description", help="Task text")
    add.add_argument("--due", help="Due date (YYYY-MM-DD)")
    add.add_argument("--AssignedTo", help="Assignee")
    add.add_argument("--priority", choices=["critical","high","medium","low"], help="Priority level")
    add.add_argument("--notes", help="Notes for the task")
    add.set_defaults(func=add_task)

    subp = subs.add_parser("subtask", help="Add a subtask under a primary")
    subp.add_argument("parent_id", type=int, help="Primary task ID")
    subp.add_argument("description", help="Subtask text")
    subp.add_argument("--due", help="Due date (YYYY-MM-DD)")
    subp.add_argument("--AssignedTo", help="Assignee")
    subp.add_argument("--priority", choices=["critical","high","medium","low"], help="Priority level")
    subp.add_argument("--notes", help="Notes for the subtask")
    subp.set_defaults(func=add_subtask)

    pend = subs.add_parser("pending", help="Mark a task/subtask in-progress (yellow ●)")
    pend.add_argument("task_id", help="ID or subtask ID (e.g. 1-1)")
    pend.set_defaults(func=pending_task)

    hold = subs.add_parser("hold", help="Mark a task/subtask on-hold (grey ⏸)")
    hold.add_argument("task_id", help="ID or subtask ID")
    hold.set_defaults(func=hold_task)

    comp = subs.add_parser("complete", help="Mark a task/subtask done (green ✓)")
    comp.add_argument("task_id", help="ID or subtask ID")
    comp.set_defaults(func=complete_task)

    dele = subs.add_parser("delete", help="Delete a task or subtask")
    dele.add_argument("task_id", help="ID or subtask ID")
    dele.set_defaults(func=delete_task)

    edt = subs.add_parser("edit", help="Edit a task or subtask")
    edt.add_argument("task_id", help="ID or subtask ID")
    edt.add_argument("--description", help="New description")
    edt.add_argument("--due", help="New due date (YYYY-MM-DD)")
    edt.add_argument("--AssignedTo", help="New assignee")
    edt.add_argument("--priority", choices=["critical","high","medium","low"], help="New priority")
    edt.add_argument("--notes", help="New notes for the task/subtask")
    edt.set_defaults(func=edit_task)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()