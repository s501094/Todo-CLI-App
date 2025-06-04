#!/home/tellis/.venv/3_12_2/bin/python3
VERSION = "2.4.1"

import argparse
import json
import os
import calendar
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

DATE_FMT = "%Y-%m-%d"
default_due = (date.today() + timedelta(days=4)).isoformat()

EXAMPLES = r"""
Examples:

  # Show app version
  todo --version

  # Add a primary task (with optional due date, assignee, notes, tags, categories)
  todo new "Write report" --due 2024-06-10 --AssignedTo Alice --priority high \
    --notes "Include exec summary" --tags work urgent --categories business reports

  # Add a subtask under task 1
  todo subtask 1 "Draft outline" --due 2024-06-12 --notes "Use Q2 template" --tags outline

  # Mark as in-progress or on-hold
  todo pending 1-1
  todo hold 1

  # Complete one or more tasks/subtasks
  todo complete 1-1 3 5

  # Delete one or more tasks/subtasks
  todo delete 9 10 11 3-2

  # Edit any field on a task/subtask
  todo edit 3 --description "Update requirements doc" \
    --due tomorrow --notes "Ask PM for changes" --tags docs requirements

  # Update (append) notes, tags, categories, or priority on a task/subtask
  todo update 3 --notes "Follow-up" --tags followup

  # Append to description or notes
  todo append 3 --AD "extra detail" --AN "more notes"

  # List only active tasks (hides done by default)
  todo list

  # List all tasks including completed
  todo list --all

  # Sort tasks
  todo list --sort due       # by due date
  todo list --sort assigned  # by assignee
  todo list --sort priority  # by priority level

  # Filter by due date
  todo list --due-today
  todo list --due-tomorrow
  todo list --due-this-month
  todo list --due-year 2025 --due-month 06

  # Show notes, tags or categories columns
  todo list --notes
  todo list --tags
  todo list --categories

  # Filter by tag or category
  todo list --tags urgent
  todo list --categories work

  # Calendar view (days with due-tasks are colored by priority)
  todo calendar              # current month
  todo calendar 2025         # full year 2025
  todo calendar 2025 06      # June 2025
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
        t.setdefault("tags", [])
        t.setdefault("categories", [])
    return tasks


def save_tasks(tasks):
    """Persist tasks back to JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def get_all_tags_and_categories(tasks):
    tags = set()
    categories = set()
    for t in tasks:
        tags.update(t.get("tags", []))
        categories.update(t.get("categories", []))
        for sub in t.get("subtasks", []):
            tags.update(sub.get("tags", []))
            categories.update(sub.get("categories", []))
    return sorted(tags), sorted(categories)


def wrap_and_color(text, width, color=None, prefix=""):
    """
    Wrap `text` to `width`, then optionally color each line
    and prepend `prefix` to the first line.
    """
    lines = textwrap.wrap(text or "", width) or [""]
    if color:
        return "\n".join(
            (prefix if i == 0 else " " * len(prefix))
            + color + ln + Style.RESET_ALL
            for i, ln in enumerate(lines)
        )
    else:
        return "\n".join(
            (prefix if i == 0 else " " * len(prefix)) + ln
            for i, ln in enumerate(lines)
        )


def color_status(t):
    """
    Return an ANSI‐colored one‐char status:
      ✓ = done (green)
      ● = pending (yellow)
      ⏸ = hold    (grey)
      ✗ = todo    (red)
    """
    if t.get("done"):
        return Fore.GREEN + "✓" + Style.RESET_ALL
    if t.get("pending"):
        return Fore.YELLOW + "●" + Style.RESET_ALL
    if t.get("hold"):
        return Fore.LIGHTBLACK_EX + "⏸" + Style.RESET_ALL
    return Fore.RED + "✗" + Style.RESET_ALL


def color_priority(prio):
    """
    Return ANSI‐colored priority text.
    """
    p = (prio or "low").lower()
    col = {
        "critical": Fore.MAGENTA,
        "high": Fore.YELLOW,
        "medium": Fore.CYAN,
        "low": Fore.BLUE
    }.get(p, Fore.BLUE)
    return col + p + Style.RESET_ALL


def parse_id(tid):
    """
    Split “1-2” into (1, "2"), or “3” into (3, None).
    """
    parts = str(tid).split("-", 1)
    return int(parts[0]), parts[1] if len(parts) > 1 else None


def find(tasks, tid):
    """
    Given a list of tasks and a task_id or subtask_id,
    return (parent_task, subtask_dict_or_None).
    """
    pid, sid = parse_id(tid)
    for t in tasks:
        if t["id"] == pid:
            if sid:
                for sub in t["subtasks"]:
                    if sub["id"] == tid:
                        return t, sub
            return t, None
    return None, None


def change_status(args, field):
    """
    Mark one or more tasks/subtasks as done/pending/hold (depending on `field`).
    Allows `todo complete 1-1 3 4-2`, etc.
    """
    tasks = load_tasks()
    ids = args.task_id if isinstance(args.task_id, list) else [args.task_id]
    any_saved = False

    for tid in ids:
        t, sub = find(tasks, tid)
        if not t:
            print(f"ID {tid} not found.")
            continue

        target = sub or t
        if field == "done" and sub is None:
            pending_subs = [s for s in t["subtasks"] if not s.get("done")]
            if pending_subs:
                print(f"Cannot complete {tid}: {len(pending_subs)} subtasks still pending.")
                continue

        for f in ("done", "pending", "hold"):
            target[f] = (f == field)

        kind = "Subtask" if sub else "Task"
        print(f"{kind} {tid} marked {field}.")
        any_saved = True

    if any_saved:
        save_tasks(tasks)


def list_tasks(args):
    tasks = load_tasks()
    all_tags, all_categories = get_all_tags_and_categories(tasks)

    if args.due_today:
        today = date.today().isoformat()
        tasks = [t for t in tasks if t.get("due") == today]
    if args.due_tomorrow:
        tm = (date.today() + timedelta(days=1)).isoformat()
        tasks = [t for t in tasks if t.get("due") == tm]
    if args.due_this_month:
        this_month = date.today().strftime("%Y-%m")
        tasks = [t for t in tasks if t.get("due", "").startswith(this_month)]
    if getattr(args, "due_year", None) is not None and getattr(args, "due_month", None) is not None:
        def has_due_in_month(task):
            d = task.get("due")
            if d:
                try:
                    dt = date.fromisoformat(d)
                except ValueError:
                    pass
                else:
                    if dt.year == args.due_year and dt.month == args.due_month:
                        return True
            for sub in task.get("subtasks", []):
                sd = sub.get("due")
                if sd:
                    try:
                        sdt = date.fromisoformat(sd)
                    except ValueError:
                        continue
                    if sdt.year == args.due_year and sdt.month == args.due_month:
                        return True
            return False

        tasks = [t for t in tasks if has_due_in_month(t)]

    if args.tags is True:
        if all_tags:
            print("Available tags:")
            print(", ".join(all_tags))
        else:
            print("No tags found.")
        return
    if args.categories is True:
        if all_categories:
            print("Available categories:")
            print(", ".join(all_categories))
        else:
            print("No categories found.")
        return

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

    filtered = []
    for t in tasks:
        if filter_tag and not has_tag(t, filter_tag):
            continue
        if filter_cat and not has_cat(t, filter_cat):
            continue
        filtered.append(t)
    tasks = filtered

    term_w = shutil.get_terminal_size().columns
    reserved = 4 + 3 + 10 + 15 + 8 + 20
    avail = max(15, term_w - reserved)

    # Wrap notes sooner: allocate 30% of available width to notes
    if avail < 150:
        desc_w = max(10, int(avail * 0.4))
        notes_w = max(10, int((avail - desc_w) * 0.5))
    else:
        desc_w = max(10,int(avail *0.2))
        notes_w = max(10, int((avail - desc_w) * 0.3))
   
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
    show_tags = bool(filter_tag) or args.tags is not None
    show_categories = bool(filter_cat) or args.categories is not None

    for t in primaries:
        if not args.all and t.get("done"):
            continue
        tid = str(t["id"])
        due_date = t.get("due") or default_due
        assigned = t.get("AssignedTo", "Tyler Ellis")
        prio = t.get("priority", "low").lower()
        notes = t.get("notes", "")

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
            "high": Fore.YELLOW + prio + Style.RESET_ALL,
            "medium": Fore.CYAN + prio + Style.RESET_ALL
        }.get(prio, Fore.BLUE + prio + Style.RESET_ALL)

        base_row = [tid, desc_col, status_col, due_date, assigned, prio_col, notes_col]
        if show_tags:
            base_row.append(", ".join(t.get("tags", [])))
        if show_categories:
            base_row.append(", ".join(t.get("categories", [])))
        rows.append(base_row)

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
                "high": Fore.YELLOW + sprio + Style.RESET_ALL,
                "medium": Fore.CYAN + sprio + Style.RESET_ALL
            }.get(sprio, Fore.BLUE + sprio + Style.RESET_ALL)
           
            notes_lines = textwrap.wrap(sub.get("notes",""), notes_w) or [""]
            notes_col = "\n".join(notes_lines)

            sub_row = [
                "", "├─ " + s_desc, s_sym, sub.get("due", ""),
                sub.get("AssignedTo", "Tyler Ellis"), sp, notes_col
            ]
            if show_tags:
                sub_row.append(", ".join(sub.get("tags", [])))
            if show_categories:
                sub_row.append(", ".join(sub.get("categories", [])))
            rows.append(sub_row)

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


def generate_calendar(args):
    tasks = load_tasks()
    _PRIORITY_COLORS = {
        "critical": Fore.RED,
        "high": Fore.YELLOW,
        "medium": Fore.CYAN,
        "low": Fore.BLUE,
    }
    _PRIORITY_RANK = {p: i for i, p in enumerate(["critical", "high", "medium", "low"])}

    if args.year < 2024:
        print(f"Year must be {datetime.today().year} or later.")
        return

    months = list(range(1, 13)) if args.month is None else [args.month]
    if any(m not in range(1, 13) for m in months):
        print("Month must be 1–12 or omitted for full year.")
        return

    def build_due_map(year, month):
        dm = {}
        for t in tasks:
            if not t.get("done"):
                for e in ([t] + t.get("subtasks", [])):
                    d = e.get("due")
                    try:
                        dt = datetime.strptime(d, DATE_FMT).date()
                    except Exception:
                        continue
                    if dt.year == year and dt.month == month:
                        p = e.get("priority", "low").lower()
                        if (dt.day not in dm or
                                _PRIORITY_RANK[p] < _PRIORITY_RANK[dm[dt.day]]):
                            dm[dt.day] = p
        return dm

    def make_block(year, month):
        dm = build_due_map(year, month)
        w = 20
        blk = []
        blk.append(f"{calendar.month_name[month]} {year}".center(w))
        blk.append("Mo Tu We Th Fr Sa Su")
        for wk in calendar.monthcalendar(year, month):
            parts = []
            for d in wk:
                if d == 0:
                    parts.append("  ")
                elif d in dm:
                    col = _PRIORITY_COLORS[dm[d]]
                    parts.append(f"{col}{d:2d}{Style.RESET_ALL}")
                else:
                    parts.append(f"{d:2d}")
            blk.append(" ".join(parts))
        return blk

    if len(months) == 1:
        print_single_month(args.year, months[0], build_due_map(args.year, months[0]), args)
        return

    groups = [months[i:i + 3] for i in range(0, 12, 3)]
    width = 20
    spacer = "   "

    for row in groups:
        blocks = [make_block(args.year, m) for m in row]
        maxl = max(len(b) for b in blocks)
        for i in range(maxl):
            line_parts = []
            for b in blocks:
                if i < len(b):
                    line_parts.append(b[i])
                else:
                    line_parts.append(" " * width)
            print(spacer.join(line_parts))
        print()


def print_single_month(year: int, month: int, due_map: dict[int, str], args):
    _PRIORITY_COLORS = {
        "critical": Fore.RED,
        "high": Fore.YELLOW,
        "medium": Fore.CYAN,
        "low": Fore.BLUE,
    }
    _PRIORITY_RANK = {p: i for i, p in enumerate(["critical", "high", "medium", "low"])}

    width = 20
    hdr = f"{calendar.month_name[month]} {year}"
    print(hdr.center(width))
    print("Mo Tu We Th Fr Sa Su")
    for wk in calendar.monthcalendar(year, month):
        parts = []
        for d in wk:
            if d == 0:
                parts.append("  ")
            elif d in due_map:
                c = _PRIORITY_COLORS[due_map[d]]
                parts.append(f"{c}{d:2d}{Style.RESET_ALL}")
            else:
                parts.append(f"{d:2d}")
        print(" ".join(parts))
    print("\n")
    print(f"Tasks due in {calendar.month_name[month]} {year}:")
    month_args = argparse.Namespace(
        all=args.all if hasattr(args, "all") else False,
        sort=args.sort if hasattr(args, "sort") else "due",
        due_today=False,
        due_tomorrow=False,
        due_on=None,
        due_before=None,
        due_after=None,
        due_this_month=(month == date.today().month),
        due_month=month,
        due_year=year,
        filter=None,
        notes=args.notes if hasattr(args, "notes") else False,
        tags=args.tags if hasattr(args, "tags") else None,
        categories=args.categories if hasattr(args, "categories") else None,
    )
    list_tasks(month_args)


def new_task(args):
    tasks = load_tasks()
    existing_ids = [int(task["id"]) for task in tasks if "id" in task and str(task["id"]).isdigit()]
    nid = max(existing_ids, default=0) + 1
    if args.due:
        args.due = due_str(args)
    tasks.append({
        "id": nid,
        "description": args.description,
        "done": False,
        "pending": False,
        "hold": False,
        "due": args.due or default_due,
        "AssignedTo": args.AssignedTo or "Tyler Ellis",
        "priority": args.priority or "low",
        "notes": args.notes or "",
        "tags": args.tags or [],
        "categories": args.categories or [],
        "created": datetime.now().isoformat(),
        "subtasks": []
    })
    save_tasks(tasks)
    print(f"Task {nid} added.")


def add_subtask(args):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == args.parent_id:
            idx = len(t["subtasks"]) + 1
            sid = f"{t['id']}-{idx}"
            resulting_due = due_str(args) if args.due else default_due
            t["subtasks"].append({
                "id": sid,
                "description": args.description,
                "done": False,
                "pending": False,
                "hold": False,
                "due": resulting_due,
                "AssignedTo": args.AssignedTo or "Tyler Ellis",
                "priority": args.priority or "low",
                "notes": args.notes or "",
                "tags": args.tags or [],
                "categories": args.categories or [],
                "created": datetime.now().isoformat()
            })
            save_tasks(tasks)
            print(f"Subtask {sid} added under task {t['id']}.")
            return
    print(f"Parent task {args.parent_id} not found.")


def pending_task(args):
    tid = args.task_id
    tasks = load_tasks()
    if "-" in tid:
        pid, _ = tid.split("-", 1)
        for t in tasks:
            if str(t["id"]) == pid:
                for sub in t["subtasks"]:
                    if sub["id"] == tid:
                        sub["pending"] = True
                        sub["done"] = False
                        sub["hold"] = False
                        save_tasks(tasks)
                        print(f"Subtask {tid} marked pending.")
                        return
        print(f"Subtask {tid} not found.")
    else:
        for t in tasks:
            if str(t["id"]) == tid:
                t["pending"] = True
                t["done"] = False
                t["hold"] = False
                save_tasks(tasks)
                print(f"Task {tid} marked pending.")
                return
        print(f"Task {tid} not found.")


def hold_task(args):
    tid = args.task_id
    tasks = load_tasks()
    if "-" in tid:
        pid, _ = tid.split("-", 1)
        for t in tasks:
            if str(t["id"]) == pid:
                for sub in t["subtasks"]:
                    if sub["id"] == tid:
                        sub["hold"] = True
                        sub["done"] = False
                        sub["pending"] = False
                        save_tasks(tasks)
                        print(f"Subtask {tid} marked on-hold.")
                        return
        print(f"Subtask {tid} not found.")
    else:
        for t in tasks:
            if str(t["id"]) == tid:
                t["hold"] = True
                t["done"] = False
                t["pending"] = False
                save_tasks(tasks)
                print(f"Task {tid} marked on-hold.")
                return
        print(f"Task {tid} not found.")


def complete_task(args):
    ids_to_complete = args.task_id if isinstance(args.task_id, list) else [args.task_id]
    tasks = load_tasks()
    completed_any = False

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
                    incomplete_subs = [s for s in t.get("subtasks", []) if not s.get("done")]
                    if incomplete_subs:
                        print(f"Task {tid} cannot be completed: {len(incomplete_subs)} subtasks still pending.")
                        found = True
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


def update_task(args):
    tid = str(args.task_id)
    tasks = load_tasks()
    for t in tasks:
        if str(t["id"]) == tid:
            if args.description:
                t["description"] = args.description
            if args.due:
                t["due"] = due_str(args)
            if args.AssignedTo:
                t["AssignedTo"] = args.AssignedTo
            if args.priority:
                t["priority"] = args.priority
            if args.notes is not None:
                t["notes"] += ", " + args.notes
            if args.tags is not None:
                t["tags"] += args.tags or []
            if args.categories is not None:
                t["categories"] += args.categories or []
            save_tasks(tasks)
            print(f"Task {tid} has been updated.")
            return
        for sub in t["subtasks"]:
            if sub["id"] == tid:
                if args.description is not None:
                    sub["description"] = args.description
                if args.due:
                    sub["due"] = due_str(args)
                if args.AssignedTo:
                    sub["AssignedTo"] = args.AssignedTo
                if args.priority:
                    sub["priority"] = args.priority
                if args.notes is not None:
                    sub["notes"] += ", " + args.notes
                else:
                    sub["notes"] += args.notes
                if args.tags is not None:
                    sub["tags"] += args.tags or []
                if args.categories is not None:
                    sub["categories"] += args.categories or []
                save_tasks(tasks)
                print(f"Subtask {tid} updated.")
                return
    print(f"Task or subtask {tid} not found.")


def due_str(args):
    if args.due == "today":
        return date.today().isoformat()
    if args.due == "tomorrow":
        return (date.today() + timedelta(days=1)).isoformat()
    if "days" in args.due:
        return (date.today() + timedelta(days=int(args.due.split()[0]))).isoformat()
    if args.due in ("next day", "1 day"):
        return (date.today() + timedelta(days=1)).isoformat()
    if args.due in ("next week", "1 week"):
        return (date.today() + timedelta(days=7)).isoformat()
    if "weeks" in args.due:
        return (date.today() + timedelta(weeks=int(args.due.split()[0]))).isoformat()
    if args.due in ("next year", "1 year"):
        return (date.today() + timedelta(days=365)).isoformat()
    if args.due in ("next month", "1 month"):
        return (date.today() + timedelta(days=30)).isoformat()
    if "months" in args.due:
        return (date.today() + timedelta(days=int(args.due.split()[0]) * 30)).isoformat()
    return args.due


def edit_task(args):
    tid = str(args.task_id)
    tasks = load_tasks()
    for t in tasks:
        if str(t["id"]) == tid:
            if args.description:
                t["description"] = args.description
            if args.due:
                t["due"] = due_str(args)
            if args.AssignedTo:
                t["AssignedTo"] = args.AssignedTo
            if args.priority:
                t["priority"] = args.priority
            if args.notes is not None:
                t["notes"] = args.notes
            if args.tags is not None:
                t["tags"] = args.tags or []
            if args.categories is not None:
                t["categories"] = args.categories or []
            save_tasks(tasks)
            print(f"Task {tid} edited.")
            return
        for sub in t["subtasks"]:
            if sub["id"] == tid:
                if args.description:
                    sub["description"] = args.description
                if args.due:
                    sub["due"] = due_str(args)
                if args.AssignedTo:
                    sub["AssignedTo"] = args.AssignedTo
                if args.priority:
                    sub["priority"] = args.priority
                if args.notes is not None:
                    sub["notes"] = args.notes
                if args.tags is not None:
                    sub["tags"] = args.tags or []
                if args.categories is not None:
                    sub["categories"] = args.categories or []
                save_tasks(tasks)
                print(f"Subtask {tid} edited.")
                return
    print(f"Task or subtask {tid} not found.")


def append_task(args):
    """
    Append text to a task or subtask’s description or notes.
    """
    tid = str(args.task_id)
    tasks = load_tasks()
    for t in tasks:
        if str(t["id"]) == tid:
            if args.AD:
                if t["description"] is not None:
                    t["description"] += " " + (" ".join(args.AD))
                else:
                    t["description"] = " ".join(args.AD)
                save_tasks(tasks)
                print(f"Appended to task {tid} description.")
                return
            if args.AN:
                if t["notes"] is not None:
                    t["notes"] += " " + (" ".join(args.AN))
                else:
                    t["notes"] = " ".join(args.AN)
                save_tasks(tasks)
                print(f"Appended to task {tid} notes.")
                return
        for sub in t.get("subtasks", []):
            if sub["id"] == tid:
                if args.AD:
                    sub["description"] += " " + (" ".join(args.AD))
                    save_tasks(tasks)
                    print(f"Appended to subtask {tid} description.")
                    return
                if args.AN:
                    sub["notes"] += " " + (" ".join(args.AN))
                    save_tasks(tasks)
                    print(f"Appended to subtask {tid} notes.")
                    return
    print(f"Task or subtask {tid} not found.")


def main():
    parser = argparse.ArgumentParser(
        prog="todo",
        description=(
            "A CLI based To-Do App for those that prefer to live in the terminal. This comes with subtasks, status, due dates, notes, tags,/ "
            "categories, and rich sorting."
        ),
        epilog=EXAMPLES,
        formatter_class=RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subs = parser.add_subparsers(dest="command", required=True)

    commands = {
        "calendar": {
            "func": generate_calendar,
            "help": "Show calendar for current month or year",
            "args": [
                (["year"], {
                    "nargs": "?",
                    "type": int,
                    "default": date.today().year,
                    "help": "Year to display (>=2024; default is current year)"
                }),
                (["month"], {
                    "nargs": "?",
                    "type": int,
                    "default": None,
                    "help": "Month 1–12; omit to print all 12 months"
                })
            ]
        },
        "list": {
            "func": list_tasks,
            "help": "List tasks & subtasks",
            "args": [
                (["--all"], {"action": "store_true", "help": "Include completed"}),
                (["--sort"], {"choices": ["due", "assigned", "priority", "id"], "default": "id", "help": "Sort primaries"}),
                (["--notes"], {"action": "store_true", "help": "Display notes"}),
                (["--tags"], {"nargs": "?", "const": True, "metavar": "TAG", "help": "Filter by tag"}),
                (["--categories"], {"nargs": "?", "const": True, "metavar": "CAT", "help": "Filter by category"}),
                (["--due-today"], {"action": "store_true", "help": "Only show tasks due today"}),
                (["--due-tomorrow"], {"action": "store_true", "help": "Only show tasks due tomorrow"}),
                (["--due-this-month"], {"action": "store_true", "help": "Only show tasks due this month"}),
                (["--due-year"], {"type": int, "help": "Only show tasks due in this year"}),
                (["--due-month"], {"type": int, "help": "Only show tasks due in this month (1–12)"})
            ]
        },
        "new": {
            "func": new_task,
            "help": "Add a primary task",
            "args": [
                (["description"], {}),
                (["--due"], {}),
                (["--AssignedTo"], {}),
                (["--priority"], {"choices": ["critical", "high", "medium", "low"]}),
                (["--notes"], {}),
                (["--tags"], {"nargs": "*"}),
                (["--categories"], {"nargs": "*"})
            ]
        },
        "subtask": {
            "func": add_subtask,
            "help": "Add a subtask",
            "args": [
                (["parent_id"], {"type": int}),
                (["description"], {}),
                (["--due"], {}),
                (["--AssignedTo"], {}),
                (["--priority"], {"choices": ["critical", "high", "medium", "low"]}),
                (["--notes"], {}),
                (["--tags"], {"nargs": "*"}),
                (["--categories"], {"nargs": "*"})
            ]
        },
        "pending": {
            "func": pending_task,
            "help": "Mark in-progress",
            "args": [(["task_id"], {})]
        },
        "hold": {
            "func": hold_task,
            "help": "Mark on-hold",
            "args": [(["task_id"], {})]
        },
        "complete": {
            "func": complete_task,
            "help": "Mark done",
            "args": [(["task_id"], {"nargs": "+"})]
        },
        "delete": {
            "func": delete_task,
            "help": "Delete task/subtask",
            "args": [(["task_id"], {"nargs": "+"})]
        },
        "edit": {
            "func": edit_task,
            "help": "Edit task/subtask (overwrite fields)",
            "args": [
                (["task_id"], {}),
                (["--description"], {}),
                (["--due"], {}),
                (["--AssignedTo"], {}),
                (["--priority"], {"choices": ["critical", "high", "medium", "low"]}),
                (["--notes"], {}),
                (["--tags"], {"nargs": "*"}),
                (["--categories"], {"nargs": "*"})
            ]
        },
        "update": {
            "func": update_task,
            "help": "Update task/subtask (append to fields)",
            "args": [
                (["task_id"], {}),
                (["--description"], {}),
                (["--due"], {}),
                (["--AssignedTo"], {}),
                (["--priority"], {"choices": ["critical", "high", "medium", "low"]}),
                (["--notes"], {}),
                (["--tags"], {"nargs": "*"}),
                (["--categories"], {"nargs": "*"})
            ]
        },
        "append": {
            "func": append_task,
            "help": "Append to task/subtask description or notes",
            "args": [
                (["task_id"], {}),
                (["--AD"], {
                    "action": "append",
                    "metavar": "WORD",
                    "nargs": "+",
                    "help": "Words to append to the description"
                }),
                (["--AN"], {
                    "metavar": "WORD",
                    "nargs": "+",
                    "help": "Words to append to the notes"
                }),
                (["--tags"], {"nargs": "*"}),
                (["--categories"], {"nargs": "*"})
            ]
        }
    }

    for name, spec in commands.items():
        sp = subs.add_parser(name, help=spec["help"], formatter_class=RawDescriptionHelpFormatter)
        for flags, params in spec["args"]:
            sp.add_argument(*flags, **params)
        sp.set_defaults(func=spec["func"])

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Catch Ctrl+C anywhere and exit cleanly
        print("\nExiting. Goodbye!")