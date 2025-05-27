#!/home/tellis/.venv/3_12_2/bin/python3
VERSION = "2.0.2"

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

  # Show app version
  todo --version

  # Add a primary task (with optional due date, assignee, notes, tags, or categories)
  todo add "Write report" --due 2024-06-10 --AssignedTo Alice --priority high --notes "Include exec summary" --tags work urgent --categories business reports

  # Add a subtask under task 1
  todo subtask 1 "Draft outline" --due 2024-06-12 --notes "Use Q2 template" --tags outline

  # Mark as in-progress or on-hold
  todo pending 1-1
  todo hold 1

  # Complete tasks (supports multiple at once)
  todo complete 1-1 3
  todo complete 2-2 4

  # Edit a task or subtask (any field)
  todo edit 3 --description "Update requirements doc" --notes "Ask PM for changes" --tags docs requirements

  # Delete one or more tasks or subtasks
  todo delete 9 10 11 3-2

  # List active tasks (default hides done)
  todo list

  # List ALL tasks including completed
  todo list --all

  # Sort tasks by due date, assignee, or priority
  todo list --sort due
  todo list --sort assigned
  todo list --sort priority

  # Show all available tags or categories
  todo list --tags
  todo list --categories

  # Filter tasks by tag or category (show only tasks with these)
  todo list --tags urgent review
  todo list --categories work personal

  # Show tags/categories columns in output (even when not filtering)
  todo list --tags --categories

  # Show notes column
  todo list --notes

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


def get_all_tags_and_categories(tasks):
    tags = set()
    categories = set()
    for t in tasks:
        for tag in t.get("tags", []):
            tags.add(tag)
        for cat in t.get("categories", []):
            categories.add(cat)
        for sub in t.get("subtasks", []):
            for tag in sub.get("tags", []):
                tags.add(tag)
            for cat in sub.get("categories", []):
                categories.add(cat)
    return sorted(tags), sorted(categories)

def list_tasks(args):
    tasks = load_tasks()
    all_tags, all_categories = get_all_tags_and_categories(tasks)

    # ─── Handle --tags / --categories special cases ──────────────
    if args.tags is True:  # --tags provided, but no value
        if all_tags:
            print("Available tags:")
            print(", ".join(all_tags))
        else:
            print("No tags found.")
        return
    if args.categories is True:  # --categories provided, but no value
        if all_categories:
            print("Available categories:")
            print(", ".join(all_categories))
        else:
            print("No categories found.")
        return

    # ─── Filter by tag or category ───────────────────────────────
    filter_tag = args.tags if isinstance(args.tags, str) else None
    filter_cat = args.categories if isinstance(args.categories, str) else None

    def has_tag(task, tag):
        if tag in (task.get("tags") or []):
            return True
        for sub in task.get("subtasks", []):
            if tag in (sub.get("tags") or []):
                return True
        return False

    def has_cat(task, cat):
        if cat in (task.get("categories") or []):
            return True
        for sub in task.get("subtasks", []):
            if cat in (sub.get("categories") or []):
                return True
        return False
    filtered_tasks = []
    for t in tasks:
        if filter_tag and not has_tag(t, filter_tag):
            continue
        if filter_cat and not has_cat(t, filter_cat):
            continue
        filtered_tasks.append(t)
    tasks = filtered_tasks

    # ─── Build Tabulate Table ────────────────────────────────────
    term_w     = shutil.get_terminal_size().columns
    reserved   = 4 + 3 + 10 + 15 + 8 + 20
    avail      = max(20, term_w - reserved)
    desc_w     = max(10, int(avail * 0.6))
    notes_w    = max(10, avail - desc_w)

    def primary_key(t):
        if args.sort == "due":
            ds = t.get("due") or default_due
            try:
                return datetime.strptime(ds, DATE_FMT)
            except ValueError:
                return datetime.today()
        if args.sort == "assigned":
            return t.get("AssignedTo", "").lower()
        if args.sort == "priority":
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            return order.get(t.get("priority", "low").lower(), 99)
        return t["id"]

    primaries = sorted(tasks, key=primary_key)
    rows = []
    show_tags = bool(filter_tag) or ('tags' in args and args.tags)  # show column if filtering or explicit
    show_categories = bool(filter_cat) or ('categories' in args and args.categories)

    for t in primaries:
        if not args.all and t.get("done"):
            continue
        tid      = str(t["id"])
        due_date = t.get("due") or default_due
        assigned = t.get("AssignedTo", "Tyler Ellis")
        prio     = t.get("priority", "low").lower()
        notes    = t.get("notes", "")

        desc_lines = textwrap.wrap(t["description"], desc_w) or [""]
        if t.get("done"):
            status_col = Fore.GREEN + "✓" + Style.RESET_ALL
            desc_col = "\n".join(Fore.GREEN + ln + Style.RESET_ALL for ln in desc_lines)
        elif t.get("hold"):
            status_col = Fore.LIGHTBLACK_EX + "⏸" + Style.RESET_ALL
            desc_col = "\n".join(Fore.LIGHTBLACK_EX + ln + Style.RESET_ALL for ln in desc_lines)
        elif t.get("pending"):
            status_col = Fore.YELLOW + "●" + Style.RESET_ALL
            desc_col = "\n".join(Fore.YELLOW + ln + Style.RESET_ALL for ln in desc_lines)
        else:
            status_col = Fore.RED + "✗" + Style.RESET_ALL
            desc_col = "\n".join(Fore.RED + ln + Style.RESET_ALL for ln in desc_lines)

        notes_lines = textwrap.wrap(notes, notes_w) or [""]
        notes_col = "\n".join(notes_lines)

        prio_col = {
            "critical": Fore.MAGENTA + prio + Style.RESET_ALL,
            "high":     Fore.YELLOW + prio + Style.RESET_ALL,
            "medium":   Fore.CYAN + prio + Style.RESET_ALL,
        }.get(prio, Fore.BLUE + prio + Style.RESET_ALL)

        base_row = [tid, desc_col, status_col, due_date, assigned, prio_col, notes_col]
        if show_tags:
            base_row.append(", ".join(t.get("tags", [])))
        if show_categories:
            base_row.append(", ".join(t.get("categories", [])))
        rows.append(base_row)

        # Subtasks
        for sub in sorted(t["subtasks"], key=lambda s: int(s["id"].split("-", 1)[1])):
            if not args.all and sub.get("done"):
                continue
            sub_lines = textwrap.wrap(sub["description"], desc_w) or [""]
            if sub.get("done"):
                s_sym = Fore.GREEN + "✓" + Style.RESET_ALL
                s_desc = "\n".join(Fore.GREEN + ln + Style.RESET_ALL for ln in sub_lines)
            elif sub.get("hold"):
                s_sym = Fore.LIGHTBLACK_EX + "⏸" + Style.RESET_ALL
                s_desc = "\n".join(Fore.LIGHTBLACK_EX + ln + Style.RESET_ALL for ln in sub_lines)
            elif sub.get("pending"):
                s_sym = Fore.YELLOW + "●" + Style.RESET_ALL
                s_desc = "\n".join(Fore.YELLOW + ln + Style.RESET_ALL for ln in sub_lines)
            else:
                s_sym = Fore.RED + "✗" + Style.RESET_ALL
                s_desc = "\n".join(Fore.RED + ln + Style.RESET_ALL for ln in sub_lines)
            sprio = sub.get("priority", "low").lower()
            sp = {
                "critical": Fore.MAGENTA + sprio + Style.RESET_ALL,
                "high":     Fore.YELLOW + sprio + Style.RESET_ALL,
                "medium":   Fore.CYAN + sprio + Style.RESET_ALL,
            }.get(sprio, Fore.BLUE + sprio + Style.RESET_ALL)

            sub_row = ["", "├─ " + s_desc, s_sym, sub.get("due", ""), sub.get("AssignedTo", "Tyler Ellis"),
                       sp, sub.get("notes", "")]
            if show_tags:
                sub_row.append(", ".join(sub.get("tags", [])))
            if show_categories:
                sub_row.append(", ".join(sub.get("categories", [])))
            rows.append(sub_row)

    # Build headers dynamically
    headers = ["ID", "Description", "Status", "Due Date", "AssignedTo", "Priority", "Notes"]
    if show_tags:
        headers.append("Tags")
    if show_categories:
        headers.append("Categories")

    if not rows:
        print("No tasks to show.")
        return

    print(tabulate(
        rows,
        headers=headers,
        colalign=("center", "left", "center", "center", "left", "center", "left") + ("left",) * (len(headers) - 7),
        stralign="left",
        tablefmt="fancy_grid"
    ))

def add_task(args):
    t = load_tasks()
    existing_ids = [int(task["id"]) for task in t if "id" in task and str(task["id"]).isdigit()]
    nid = max(existing_ids, default=0) + 1
    if args.due:
        if args.due == "today":
            args.due = date.today().isoformat()
        elif args.due == "tomorrow":
            args.due = (date.today() + timedelta(days=1)).isoformat()
        elif "days" in args.due:
            args.due = (date.today() + timedelta(days=int(args.due.split()[0]))).isoformat()
        elif args.due == "nextday" or args.due == "1 day":
            args.due = (date.today() + timedelta(days=1)).isoformat()
        elif args.due == "nextweek" or args.due == "1 week":
            args.due = (date.today() + timedelta(days=7)).isoformat()
        elif "weeks" in args.due:
            args.due = (date.today() + timedelta(weeks=int(args.due.split()[0]))).isoformat()
        elif args.due == "nextyear" or args.due == "1 year":
            args.due = (date.today() + timedelta(days=366)).isoformat()  
        elif args.due == "nextmonth" or args.due == "2 month":
            args.due = (date.today() + timedelta(days=30)).isoformat()
        elif "months" in args.due:
            args.due = (date.today() + timedelta(days=int(args.due.split()[0]) * 30)).isoformat()
        elif args.due == "nextweek" or args.due == "1 week":
            args.due = (date.today() + timedelta(days=7)).isoformat()
        elif args.due == "nextmonth" or args.due == "1 month":
            args.due = (date.today() + timedelta(days=30)).isoformat()
        else:
            args.due = args.due
    t.append({
        "id": nid,
        "description": args.description,
        "done":        False,
        "pending":     False,
        "hold":        False,
        "due":         args.due or default_due,
        "AssignedTo":  args.AssignedTo or "Tyler Ellis",
        "priority":    args.priority or "low",
        "notes":       args.notes or "",
        "tags":        args.tags or [],
        "categories":  args.categories or [],
        "created":     datetime.now().isoformat(),
        "subtasks":    []
    })
    save_tasks(t)
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
                "notes":       args.notes or "",
                "tags":        args.tags or [],
                "categories":  args.categories or [],
                "created":     datetime.now().isoformat()
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
    ids_to_complete = [tid] if isinstance(tid, str) else tid
    completed_any = False

    if not ids_to_complete:
        print("No task ID provided.")
        return

    for tid in ids_to_complete:
        if "-" in tid:
            pid, _ = tid.split("-", 1)
            found = False
            for t in tasks:
                if str(t["id"]) == pid:
                    for sub in t["subtasks"]:
                        if sub["id"] == tid:
                            sub["done"] = True
                            sub["pending"] = False
                            sub["hold"] = False
                            save_tasks(tasks)
                            print(f"Subtask {tid} marked complete.")
                            found = True
                            break
            if not found:
                print(f"Subtask {tid} not found.")
        else:
            found = False
            for t in tasks:
                if str(t["id"]) == tid:
                    # Optionally: don't allow if subtasks are incomplete
                    incomplete_subs = [s for s in t.get("subtasks", []) if not s.get("done")]
                    if incomplete_subs:
                        print(f"Task {tid} cannot be completed: {len(incomplete_subs)} subtasks still pending.")
                        found = True  # Found, but not marked complete
                        break
                    t["done"] = True
                    t["pending"] = False
                    t["hold"] = False
                    completed_any = True
                    print(f"Task {tid} marked complete.")
                    found = True
                    break
            if not found:
                print(f"Task {tid} not found.")
    if completed_any:
        save_tasks(tasks)


def delete_task(args):
    tasks = load_tasks()
    ids_to_delete = args.task_id
    deleted_any = False

    for tid in ids_to_delete:
        if "-" in tid:
            pid, _ = tid.split("-", 1)
            found = False
            for t in tasks:
                if str(t["id"]) == pid:
                    before = len(t["subtasks"])
                    t["subtasks"] = [s for s in t["subtasks"] if s["id"] != tid]
                    if len(t["subtasks"]) < before:
                        found = True
                        deleted_any = True
                        print(f"Subtask {tid} deleted.")
            if not found:
                print(f"Subtask {tid} not found.")
        else:
            before = len(tasks)
            tasks = [t for t in tasks if str(t["id"]) != tid]
            if len(tasks) < before:
                deleted_any = True
                print(f"Task {tid} deleted (and its subtasks).")
            else:
                print(f"Task {tid} not found.")
    if deleted_any:
        save_tasks(tasks)

def edit_task(args):
    tid   = str(args.task_id)
    tasks = load_tasks()
    for t in tasks:
        if str(t["id"]) == tid:
            if args.description: t["description"] = args.description
            if args.due:
                if args.due == "today":
                    t["due"] = date.today().isoformat()
                elif args.due == "tomorrow":
                    t["due"] = (date.today() + timedelta(days=1)).isoformat()
                elif "days" in args.due:
                    t["due"] = (date.today() + timedelta(days=int(args.due.split()[0]))).isoformat()
                elif args.due == "nextday" or args.due == "1 day":
                    t["due"] = (date.today() + timedelta(days=1)).isoformat()
                elif args.due == "nextweek" or args.due == "1 week":
                    t["due"] = (date.today() + timedelta(days=7)).isoformat()
                elif "weeks" in args.due:
                    t["due"] = (date.today() + timedelta(weeks=int(args.due.split()[0]))).isoformat()
                elif args.due == "nextyear" or args.due == "1 year":
                    t["due"] = (date.today() + timedelta(days=365)).isoformat()  
                elif args.due == "nextmonth" or args.due == "1 month":
                    t["due"] = (date.today() + timedelta(days=30)).isoformat()
                elif "months" in args.due:
                    t["due"] = (date.today() + timedelta(days=int(args.due.split()[0]) * 30)).isoformat()
                elif args.due == "nextweek" or args.due == "1 week":
                    t["due"] = (date.today() + timedelta(days=7)).isoformat()
                elif args.due == "nextmonth" or args.due == "1 month":
                    t["due"] = (date.today() + timedelta(days=30)).isoformat()
                else:
                    t["due"] = args.due
            if args.AssignedTo:  t["AssignedTo"] = args.AssignedTo
            if args.priority:    t["priority"] = args.priority
            if args.notes is not None:
                t["notes"] = args.notes
            if args.tags is not None:
                t["tags"] = args.tags or []
            if args.categories is not None:
                t["categories"] = args.categories or []
            
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
                if args.tags is not None:
                    sub["tags"] = args.tags or []
                if args.categories is not None:
                    sub["categories"] = args.categories or []
                save_tasks(tasks)
                print(f"Subtask {tid} updated.")
                return
    print(f"Task or subtask {tid} not found.")

def main():
    parser = argparse.ArgumentParser(
        prog="todo",
        description="A CLI based To-Do App\n"
                    "Supports: hierarchical subtasks, status (done/pending/hold), due dates, notes, "
                    "tags, categories, assignment, rich sorting, batch complete/delete, and more.",
        epilog=EXAMPLES,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}",
                        help="Show program version and exit")


    subs = parser.add_subparsers(dest="command", required=True)

    # List tasks & subtasks
    lst = subs.add_parser("list", help="List tasks & subtasks", formatter_class=RawDescriptionHelpFormatter)
    lst.add_argument("--all", action="store_true", help="Include completed")
    lst.add_argument("--sort", choices=["due","assigned","priority","id"], default="id",
                     help="Sort primaries by this field")
    lst.add_argument("--notes", action="store_true", help="Show notes in output")
    lst.add_argument("--tags", nargs="?", const=True, metavar="TAG", help="Show all tags, or filter by TAG")
    lst.add_argument("--categories",nargs="?", const=True, metavar="CATEGORIES", help="Show categories in output")
    lst.set_defaults(func=list_tasks)

    # Add tasks
    add = subs.add_parser("add", help="Add a primary task")
    add.add_argument("description", help="Task text")
    add.add_argument("--due", help="Due date (YYYY-MM-DD)")
    add.add_argument("--AssignedTo", help="Assignee")
    add.add_argument("--priority", choices=["critical","high","medium","low"], help="Priority level")
    add.add_argument("--notes", help="Notes for the task")
    add.add_argument("--tags", nargs="*", help="Tags for the task")
    add.add_argument("--categories", nargs="*", help="Categories for the task")
    add.set_defaults(func=add_task)

    # Add subtasks
    subp = subs.add_parser("subtask", help="Add a subtask under a primary")
    subp.add_argument("parent_id", type=int, help="Primary task ID")
    subp.add_argument("description", help="Subtask text")
    subp.add_argument("--due", help="Due date (YYYY-MM-DD)")
    subp.add_argument("--AssignedTo", help="Assignee")
    subp.add_argument("--priority", choices=["critical","high","medium","low"], help="Priority level")
    subp.add_argument("--notes", help="Notes for the subtask")
    subp.add_argument("--tags", nargs="*", help="Tags for the subtask")
    subp.add_argument("--categories", nargs="*", help="Categories for the subtask")
    subp.set_defaults(func=add_subtask)

    # Task status changes
    pend = subs.add_parser("pending", help="Mark a task/subtask in-progress (yellow ●)")
    pend.add_argument("task_id", help="ID or subtask ID (e.g. 1-1)")
    pend.set_defaults(func=pending_task)

    hold = subs.add_parser("hold", help="Mark a task/subtask on-hold (grey ⏸)")
    hold.add_argument("task_id", help="ID or subtask ID")
    hold.set_defaults(func=hold_task)

    comp = subs.add_parser("complete", help="Mark a task/subtask done (green ✓)")
    comp.add_argument("task_id", nargs="+", help="ID or subtask ID")
    comp.set_defaults(func=complete_task)

    # Delete tasks or subtasks
    dele = subs.add_parser("delete", help="Delete a task or subtask")
    dele.add_argument("task_id", nargs="+", help="ID or subtask ID")
    dele.set_defaults(func=delete_task)

    # Edit tasks or subtasks
    edt = subs.add_parser("edit", help="Edit a task or subtask")
    edt.add_argument("task_id", help="ID or subtask ID")
    edt.add_argument("--description", help="New description")
    edt.add_argument("--due", help="New due date (YYYY-MM-DD)")
    edt.add_argument("--AssignedTo", help="New assignee")
    edt.add_argument("--priority", choices=["critical","high","medium","low"], help="New priority")
    edt.add_argument("--notes", help="New notes for the task/subtask")
    edt.add_argument("--tags", nargs="*", help="New tags for the task/subtask")
    edt.add_argument("--categories", nargs="*", help="New categories for the task/subtask")
    edt.set_defaults(func=edit_task)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()