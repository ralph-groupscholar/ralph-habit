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


def _window_dates(end_date: date, days: int) -> List[date]:
    return [end_date - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _count_window_checkins(checkins: Set[str], end_date: date, days: int) -> int:
    window = _window_dates(end_date, days)
    return sum(1 for day in window if _format_date(day) in checkins)


def _date_range(start_date: date, end_date: date) -> List[date]:
    if end_date < start_date:
        return []
    span = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(span + 1)]


def _resolve_dates(args: argparse.Namespace) -> Optional[List[date]]:
    if args.date and (args.start or args.end):
        print("Use either --date or --start/--end, not both.")
        return None
    if args.start or args.end:
        start_date = _parse_date(args.start) if args.start else _parse_date(args.end)
        end_date = _parse_date(args.end) if args.end else start_date
        dates = _date_range(start_date, end_date)
        if not dates:
            print("End date must be on or after start date.")
            return None
        return dates
    target_date = _today_local() if args.date is None else _parse_date(args.date)
    return [target_date]


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
    dates = _resolve_dates(args)
    if dates is None:
        return
    checkins = _get_checkin_set(item)
    added = 0
    for target_date in dates:
        date_key = _format_date(target_date)
        if date_key not in checkins:
            checkins.add(date_key)
            added += 1
    item["checkins"] = sorted(checkins)
    _save_items(items)
    if added == 0:
        print(f"No new check-ins added for habit #{args.id}.")
        return
    if len(dates) == 1:
        print(f"Checked in habit #{args.id}: {item.get('title', '')} ({_format_date(dates[0])})")
        return
    print(
        f"Checked in habit #{args.id}: {item.get('title', '')} "
        f"({added} new from {_format_date(dates[0])} to {_format_date(dates[-1])})"
    )


def cmd_uncheck(args: argparse.Namespace) -> None:
    items = _load_items()
    item = _get_item(items, args.id)
    if not item:
        print(f"Habit #{args.id} not found.")
        return
    dates = _resolve_dates(args)
    if dates is None:
        return
    checkins = _get_checkin_set(item)
    removed = 0
    for target_date in dates:
        date_key = _format_date(target_date)
        if date_key in checkins:
            checkins.remove(date_key)
            removed += 1
    item["checkins"] = sorted(checkins)
    _save_items(items)
    if removed == 0:
        print(f"No check-ins removed for habit #{args.id}.")
        return
    if len(dates) == 1:
        print(f"Removed check-in for habit #{args.id} on {_format_date(dates[0])}.")
        return
    print(
        f"Removed {removed} check-ins for habit #{args.id} "
        f"from {_format_date(dates[0])} to {_format_date(dates[-1])}."
    )


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


def cmd_report(args: argparse.Namespace) -> None:
    items = _load_items()
    if not args.all:
        items = [i for i in items if not i.get("done")]
    if not items:
        print("No habits yet.")
        return
    if args.days <= 0:
        print("Days must be at least 1.")
        return
    end_date = _today_local() if args.date is None else _parse_date(args.date)
    window = _window_dates(end_date, args.days)
    window_labels = f"{_format_date(window[0])} → {_format_date(window[-1])}"
    total_possible = len(items) * args.days
    total_checkins = 0

    print(f"Report window: {window_labels} ({args.days} days)")
    for item in items:
        checkins = _get_checkin_set(item)
        count = _count_window_checkins(checkins, end_date, args.days)
        total_checkins += count
        rate = (count / args.days) * 100
        last_checkin = max(checkins) if checkins else "-"
        streaks = _compute_streaks(checkins, end_date) if checkins else {"current": 0, "longest": 0}
        print(
            f"{item['id']:>3} {item.get('title', '')} | "
            f"{count}/{args.days} ({rate:.0f}%) | "
            f"current {streaks['current']} | "
            f"best {streaks['longest']} | "
            f"last {last_checkin}"
        )

    overall_rate = (total_checkins / total_possible) * 100 if total_possible else 0
    print(f"Overall check-ins: {total_checkins}/{total_possible} ({overall_rate:.0f}%)")


def cmd_history(args: argparse.Namespace) -> None:
    items = _load_items()
    item = _get_item(items, args.id)
    if not item:
        print(f"Habit #{args.id} not found.")
        return
    if args.days <= 0:
        print("Days must be at least 1.")
        return
    end_date = _today_local() if args.date is None else _parse_date(args.date)
    window = _window_dates(end_date, args.days)
    checkins = _get_checkin_set(item)
    window_labels = f"{_format_date(window[0])} → {_format_date(window[-1])}"
    print(f"History: {item.get('title', '')} ({window_labels})")
    for day in window:
        day_key = _format_date(day)
        mark = "✓" if day_key in checkins else "·"
        print(f"{day_key} {mark}")


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
    checkin.add_argument("--start", help="Start date for range (YYYY-MM-DD)")
    checkin.add_argument("--end", help="End date for range (YYYY-MM-DD)")
    checkin.set_defaults(func=cmd_checkin)

    uncheck = sub.add_parser("uncheck", help="Remove a check-in for a habit")
    uncheck.add_argument("id", type=int, help="Habit id")
    uncheck.add_argument("--date", help="Override date (YYYY-MM-DD)")
    uncheck.add_argument("--start", help="Start date for range (YYYY-MM-DD)")
    uncheck.add_argument("--end", help="End date for range (YYYY-MM-DD)")
    uncheck.set_defaults(func=cmd_uncheck)

    streak = sub.add_parser("streak", help="Show streak stats for a habit")
    streak.add_argument("id", type=int, help="Habit id")
    streak.add_argument("--date", help="Override date (YYYY-MM-DD)")
    streak.set_defaults(func=cmd_streak)

    stats = sub.add_parser("stats", help="Show habit stats")
    stats.set_defaults(func=cmd_stats)

    report = sub.add_parser("report", help="Weekly or custom habit summary")
    report.add_argument("--days", type=int, default=7, help="Number of days to include")
    report.add_argument("--date", help="Override end date (YYYY-MM-DD)")
    report.add_argument("--all", action="store_true", help="Include completed habits")
    report.set_defaults(func=cmd_report)

    history = sub.add_parser("history", help="Show daily check-ins for a habit")
    history.add_argument("id", type=int, help="Habit id")
    history.add_argument("--days", type=int, default=14, help="Number of days to include")
    history.add_argument("--date", help="Override end date (YYYY-MM-DD)")
    history.set_defaults(func=cmd_history)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
