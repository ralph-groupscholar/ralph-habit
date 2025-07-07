#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime
from typing import List, Dict, Any

DATA_PATH = os.path.expanduser("~/.ralph-habit.json")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _load_items() -> List[Dict[str, Any]]:
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return data


def _save_items(items: List[Dict[str, Any]]) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, sort_keys=True)


def _next_id(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 1
    return max(item.get("id", 0) for item in items) + 1


def cmd_add(args: argparse.Namespace) -> None:
    items = _load_items()
    item = {
        "id": _next_id(items),
        "title": args.title.strip(),
        "created_at": _now_iso(),
        "done": False,
    }
    items.append(item)
    _save_items(items)
    print(f"Added habit #{item['id']}: {item['title']}")


def cmd_list(args: argparse.Namespace) -> None:
    items = _load_items()
    if not args.all:
        items = [i for i in items if not i.get("done")]
    if not items:
        print("No habits yet.")
        return
    for item in items:
        status = "✓" if item.get("done") else "·"
        print(f"{item['id']:>3} {status} {item.get('title', '')}")


def cmd_done(args: argparse.Namespace) -> None:
    items = _load_items()
    for item in items:
        if item.get("id") == args.id:
            if item.get("done"):
                print(f"Habit #{args.id} is already done.")
                return
            item["done"] = True
            item["done_at"] = _now_iso()
            _save_items(items)
            print(f"Completed habit #{args.id}: {item.get('title', '')}")
            return
    print(f"Habit #{args.id} not found.")


def cmd_delete(args: argparse.Namespace) -> None:
    items = _load_items()
    new_items = [i for i in items if i.get("id") != args.id]
    if len(new_items) == len(items):
        print(f"Habit #{args.id} not found.")
        return
    _save_items(new_items)
    print(f"Deleted habit #{args.id}.")


def cmd_rename(args: argparse.Namespace) -> None:
    items = _load_items()
    for item in items:
        if item.get("id") == args.id:
            old_title = item.get("title", "")
            item["title"] = args.title.strip()
            _save_items(items)
            print(f"Renamed habit #{args.id}: {old_title} -> {item['title']}")
            return
    print(f"Habit #{args.id} not found.")


def cmd_stats(_: argparse.Namespace) -> None:
    items = _load_items()
    total = len(items)
    completed = sum(1 for item in items if item.get("done"))
    active = total - completed
    if total == 0:
        print("No habits yet.")
        return
    print(f"Total: {total}")
    print(f"Active: {active}")
    print(f"Completed: {completed}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local-first habit tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add a new habit")
    add.add_argument("title", help="Habit title")
    add.set_defaults(func=cmd_add)

    list_cmd = sub.add_parser("list", help="List habits")
    list_cmd.add_argument("--all", action="store_true", help="Include completed habits")
    list_cmd.set_defaults(func=cmd_list)

    done = sub.add_parser("done", help="Mark a habit as done")
    done.add_argument("id", type=int, help="Habit id")
    done.set_defaults(func=cmd_done)

    delete = sub.add_parser("delete", help="Delete a habit")
    delete.add_argument("id", type=int, help="Habit id")
    delete.set_defaults(func=cmd_delete)

    rename = sub.add_parser("rename", help="Rename a habit")
    rename.add_argument("id", type=int, help="Habit id")
    rename.add_argument("title", help="New habit title")
    rename.set_defaults(func=cmd_rename)

    stats = sub.add_parser("stats", help="Show habit stats")
    stats.set_defaults(func=cmd_stats)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
