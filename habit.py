#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set

DATA_PATH = os.path.expanduser("~/.ralph-habit.json")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _today_local() -> date:
    return datetime.now().date()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _format_date(value: date) -> str:
    return value.isoformat()


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    if "checkins" not in item or not isinstance(item.get("checkins"), list):
        item["checkins"] = []
    return item


def _load_items() -> List[Dict[str, Any]]:
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [_normalize_item(i) for i in data if isinstance(i, dict)]


def _save_items(items: List[Dict[str, Any]]) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, sort_keys=True)


def _next_id(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 1
    return max(item.get("id", 0) for item in items) + 1


def _get_item(items: List[Dict[str, Any]], habit_id: int) -> Optional[Dict[str, Any]]:
    for item in items:
        if item.get("id") == habit_id:
            return item
    return None


def _get_checkin_set(item: Dict[str, Any]) -> Set[str]:
    raw = item.get("checkins", [])
    if not isinstance(raw, list):
        return set()
    return {v for v in raw if isinstance(v, str)}


def _compute_streaks(checkins: Set[str], today: date) -> Dict[str, int]:
    dates = sorted(_parse_date(d) for d in checkins)
    if not dates:
        return {"current": 0, "longest": 0}

    longest = 1
    current_run = 1
    for idx in range(1, len(dates)):
        if dates[idx] == dates[idx - 1] + timedelta(days=1):
            current_run += 1
        else:
            longest = max(longest, current_run)
            current_run = 1
    longest = max(longest, current_run)

    current = 0
    cursor = today
    while _format_date(cursor) in checkins:
        current += 1
        cursor -= timedelta(days=1)

    return {"current": current, "longest": longest}


def cmd_add(args: argparse.Namespace) -> None:
    items = _load_items()
    item = {
        "id": _next_id(items),
        "title": args.title.strip(),
        "created_at": _now_iso(),
        "done": False,
        "checkins": [],
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
        checkins = _get_checkin_set(item)
        last_checkin = max(checkins) if checkins else "-"
        print(f"{item['id']:>3} {status} {item.get('title', '')} (last: {last_checkin})")


def cmd_done(args: argparse.Namespace) -> None:
    items = _load_items()
    item = _get_item(items, args.id)
    if item:
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
    item = _get_item(items, args.id)
    if item:
        old_title = item.get("title", "")
        item["title"] = args.title.strip()
        _save_items(items)
        print(f"Renamed habit #{args.id}: {old_title} -> {item['title']}")
        return
    print(f"Habit #{args.id} not found.")


def cmd_checkin(args: argparse.Namespace) -> None:
    items = _load_items()
    item = _get_item(items, args.id)
    if not item:
        print(f"Habit #{args.id} not found.")
        return
    if item.get("done"):
        print(f"Habit #{args.id} is archived. Rename or add a new habit to keep tracking.")
        return
    target_date = _today_local() if args.date is None else _parse_date(args.date)
    checkins = _get_checkin_set(item)
    date_key = _format_date(target_date)
    if date_key in checkins:
        print(f"Habit #{args.id} already checked in for {date_key}.")
        return
    checkins.add(date_key)
    item["checkins"] = sorted(checkins)
    _save_items(items)
    print(f"Checked in habit #{args.id}: {item.get('title', '')} ({date_key})")


def cmd_streak(args: argparse.Namespace) -> None:
    items = _load_items()
    item = _get_item(items, args.id)
    if not item:
        print(f"Habit #{args.id} not found.")
        return
    checkins = _get_checkin_set(item)
    if not checkins:
        print("No check-ins yet.")
        return
    today = _today_local() if args.date is None else _parse_date(args.date)
    streaks = _compute_streaks(checkins, today)
    print(f"Current streak: {streaks['current']} day(s)")
    print(f"Longest streak: {streaks['longest']} day(s)")
    print(f"Total check-ins: {len(checkins)}")


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
    total_checkins = sum(len(_get_checkin_set(item)) for item in items)
    print(f"Check-ins: {total_checkins}")


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

    checkin = sub.add_parser("checkin", help="Record a check-in for a habit")
    checkin.add_argument("id", type=int, help="Habit id")
    checkin.add_argument("--date", help="Override date (YYYY-MM-DD)")
    checkin.set_defaults(func=cmd_checkin)

    streak = sub.add_parser("streak", help="Show streak stats for a habit")
    streak.add_argument("id", type=int, help="Habit id")
    streak.add_argument("--date", help="Override date (YYYY-MM-DD)")
    streak.set_defaults(func=cmd_streak)

    stats = sub.add_parser("stats", help="Show habit stats")
    stats.set_defaults(func=cmd_stats)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
