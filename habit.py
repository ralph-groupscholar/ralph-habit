#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple

DATA_PATH = os.path.expanduser("~/.ralph-habit.json")
DEFAULT_PROFILE = "default"


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _today_local() -> date:
    return datetime.now().date()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _format_date(value: date) -> str:
    return value.isoformat()


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    if "checkins" not in item or not isinstance(item.get("checkins"), list):
        item["checkins"] = []
    goal = item.get("goal_per_week")
    if goal is not None and not isinstance(goal, int):
        item["goal_per_week"] = None
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


def _touch_item(item: Dict[str, Any]) -> None:
    item["updated_at"] = _now_iso()


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


def _weekday_index(label: str) -> int:
    options = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    return options[label]


def _week_window(end_date: date, week_start: str) -> Tuple[date, date]:
    start_idx = _weekday_index(week_start)
    current_idx = end_date.weekday()
    delta = (current_idx - start_idx) % 7
    start_date = end_date - timedelta(days=delta)
    end_date = start_date + timedelta(days=6)
    return start_date, end_date


def _last_checkin_date(checkins: Set[str]) -> Optional[date]:
    if not checkins:
        return None
    return max(_parse_date(value) for value in checkins)


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


def _db_profile() -> str:
    return os.environ.get("RALPH_HABIT_PROFILE", DEFAULT_PROFILE)


def _db_url() -> Optional[str]:
    return os.environ.get("DATABASE_URL") or os.environ.get("RALPH_HABIT_DB_URL")


def _get_db_connection():
    db_url = _db_url()
    if not db_url:
        print("Database sync needs DATABASE_URL or RALPH_HABIT_DB_URL.")
        return None
    try:
        import psycopg
    except ImportError:
        print("Database sync needs psycopg installed (pip install 'psycopg[binary]').")
        return None
    return psycopg.connect(db_url)


def _ensure_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ralph_habit_items (
            profile TEXT NOT NULL,
            id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            done BOOLEAN,
            done_at TEXT,
            checkins JSONB,
            PRIMARY KEY (profile, id)
        )
        """
    )


def _local_item_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(item)
    if not payload.get("created_at"):
        payload["created_at"] = _now_iso()
    if not payload.get("updated_at"):
        payload["updated_at"] = payload["created_at"]
    payload["checkins"] = sorted(_get_checkin_set(payload))
    payload["done"] = bool(payload.get("done"))
    return payload


def _compare_updated(
    local_item: Dict[str, Any], db_item: Dict[str, Any]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    local_updated = _parse_iso_datetime(local_item.get("updated_at")) or _parse_iso_datetime(
        local_item.get("created_at")
    )
    db_updated = _parse_iso_datetime(db_item.get("updated_at")) or _parse_iso_datetime(
        db_item.get("created_at")
    )
    return local_updated, db_updated


def cmd_add(args: argparse.Namespace) -> None:
    items = _load_items()
    item = {
        "id": _next_id(items),
        "title": args.title.strip(),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
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
        goal = item.get("goal_per_week")
        goal_label = f"goal: {goal}/wk" if isinstance(goal, int) else "goal: -"
        print(
            f"{item['id']:>3} {status} {item.get('title', '')} "
            f"({goal_label}, last: {last_checkin})"
        )


def cmd_done(args: argparse.Namespace) -> None:
    items = _load_items()
    item = _get_item(items, args.id)
    if item:
        if item.get("done"):
            print(f"Habit #{args.id} is already done.")
            return
        item["done"] = True
        item["done_at"] = _now_iso()
        _touch_item(item)
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
        _touch_item(item)
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
    _touch_item(item)
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
    _touch_item(item)
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
    goals = sum(1 for item in items if isinstance(item.get("goal_per_week"), int))
    print(f"With goals: {goals}")
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
        goal = item.get("goal_per_week")
        if isinstance(goal, int):
            expected = (goal * args.days) / 7
            goal_label = f"goal {goal}/wk pace {count}/{expected:.1f}"
        else:
            goal_label = "goal -"
        print(
            f"{item['id']:>3} {item.get('title', '')} | "
            f"{count}/{args.days} ({rate:.0f}%) | "
            f"current {streaks['current']} | "
            f"best {streaks['longest']} | "
            f"last {last_checkin} | "
            f"{goal_label}"
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


def cmd_sync(_: argparse.Namespace) -> None:
    items = _load_items()
    if not items:
        print("No habits to sync.")
        return
    conn = _get_db_connection()
    if conn is None:
        return
    profile = _db_profile()
    with conn:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            for item in items:
                payload = _local_item_payload(item)
                cursor.execute(
                    """
                    INSERT INTO ralph_habit_items
                        (profile, id, title, created_at, updated_at, done, done_at, checkins)
                    VALUES (%(profile)s, %(id)s, %(title)s, %(created_at)s, %(updated_at)s, %(done)s, %(done_at)s, %(checkins)s::jsonb)
                    ON CONFLICT (profile, id) DO UPDATE SET
                        title = EXCLUDED.title,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        done = EXCLUDED.done,
                        done_at = EXCLUDED.done_at,
                        checkins = EXCLUDED.checkins
                    """,
                    {
                        "profile": profile,
                        "id": payload.get("id"),
                        "title": payload.get("title", ""),
                        "created_at": payload.get("created_at"),
                        "updated_at": payload.get("updated_at"),
                        "done": payload.get("done"),
                        "done_at": payload.get("done_at"),
                        "checkins": json.dumps(payload.get("checkins", [])),
                    },
                )
    conn.close()
    print(f"Synced {len(items)} habit(s) to profile '{profile}'.")


def cmd_pull(_: argparse.Namespace) -> None:
    conn = _get_db_connection()
    if conn is None:
        return
    profile = _db_profile()
    with conn:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            cursor.execute(
                """
                SELECT id, title, created_at, updated_at, done, done_at, checkins
                FROM ralph_habit_items
                WHERE profile = %s
                ORDER BY id
                """,
                (profile,),
            )
            rows = cursor.fetchall()
    conn.close()
    if not rows:
        print(f"No habits found for profile '{profile}'.")
        return
    items = _load_items()
    local_by_id = {item.get("id"): item for item in items if isinstance(item.get("id"), int)}
    merged: List[Dict[str, Any]] = []
    merged_ids: Set[int] = set()
    for row in rows:
        db_item = {
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "done": row[4],
            "done_at": row[5],
            "checkins": row[6] if isinstance(row[6], list) else json.loads(row[6]) if row[6] else [],
        }
        local_item = local_by_id.get(db_item["id"])
        if local_item:
            local_updated, db_updated = _compare_updated(local_item, db_item)
            if db_updated and (not local_updated or db_updated > local_updated):
                merged.append(_normalize_item(db_item))
            else:
                merged.append(_normalize_item(local_item))
            merged_ids.add(db_item["id"])
        else:
            merged.append(_normalize_item(db_item))
            merged_ids.add(db_item["id"])
    for item_id, local_item in local_by_id.items():
        if item_id not in merged_ids:
            merged.append(_normalize_item(local_item))
    _save_items(merged)
    print(f"Pulled {len(rows)} habit(s) from profile '{profile}' into local store.")


def cmd_week(args: argparse.Namespace) -> None:
    items = _load_items()
    if not args.all:
        items = [i for i in items if not i.get("done")]
    if not items:
        print("No habits yet.")
        return
    target_date = _today_local() if args.date is None else _parse_date(args.date)
    start_date, end_date = _week_window(target_date, args.week_start)
    window = _date_range(start_date, end_date)
    window_labels = f"{_format_date(start_date)} → {_format_date(end_date)}"
    elapsed_days = (target_date - start_date).days + 1
    remaining_days = 7 - elapsed_days
    print(
        f"Week view ({args.week_start} start): {window_labels} "
        f"(day {elapsed_days} of 7)"
    )
    for item in items:
        checkins = _get_checkin_set(item)
        count = sum(1 for day in window if _format_date(day) in checkins)
        goal = item.get("goal_per_week")
        if isinstance(goal, int):
            remaining = max(goal - count, 0)
            needed = (
                f"need {remaining} more over {remaining_days} day(s)"
                if remaining > 0
                else "goal hit"
            )
            goal_label = f"{count}/{goal} {needed}"
        else:
            goal_label = f"{count}/-"
        print(f"{item['id']:>3} {item.get('title', '')} | {goal_label}")


def cmd_nudge(args: argparse.Namespace) -> None:
    items = _load_items()
    if not args.all:
        items = [i for i in items if not i.get("done")]
    if not items:
        print("No habits yet.")
        return
    if args.days < 0:
        print("Days must be at least 0.")
        return
    target_date = _today_local() if args.date is None else _parse_date(args.date)
    start_date, end_date = _week_window(target_date, args.week_start)
    window = _date_range(start_date, end_date)
    elapsed_days = (target_date - start_date).days + 1
    remaining_days = 7 - elapsed_days
    nudges: List[str] = []
    for item in items:
        checkins = _get_checkin_set(item)
        last_date = _last_checkin_date(checkins)
        days_since = (target_date - last_date).days if last_date else None
        stale = last_date is None or (days_since is not None and days_since >= args.days)

        count = sum(1 for day in window if _format_date(day) in checkins)
        goal = item.get("goal_per_week")
        behind_pace = False
        impossible = False
        pace_label = f"{count}/-"
        if isinstance(goal, int):
            expected = (goal * elapsed_days) / 7
            behind_pace = count + 1e-9 < expected
            remaining = max(goal - count, 0)
            impossible = remaining > remaining_days
            pace_label = f"{count}/{goal} pace {expected:.1f}"

        if not stale and not behind_pace:
            continue

        status = []
        if stale:
            if last_date is None:
                status.append("no check-ins yet")
            else:
                status.append(f"{days_since}d since last")
        if behind_pace:
            status.append("behind pace")
        if impossible:
            status.append("at risk")

        last_label = _format_date(last_date) if last_date else "-"
        nudges.append(
            f"{item['id']:>3} {item.get('title', '')} | "
            f"last {last_label} | "
            f"week {pace_label} | "
            f"{', '.join(status)}"
        )

    if not nudges:
        print("All habits are on track.")
        return
    print(
        f"Nudge view ({args.week_start} start, stale >= {args.days}d): "
        f"{_format_date(start_date)} → {_format_date(end_date)}"
    )
    for line in nudges:
        print(line)


def cmd_goal(args: argparse.Namespace) -> None:
    items = _load_items()
    item = _get_item(items, args.id)
    if not item:
        print(f"Habit #{args.id} not found.")
        return
    if args.clear:
        item["goal_per_week"] = None
        _touch_item(item)
        _save_items(items)
        print(f"Cleared goal for habit #{args.id}.")
        return
    if args.per_week == 0:
        print("Provide a goal between 1 and 7, or use --clear.")
        return
    if args.per_week < 1 or args.per_week > 7:
        print("Goal per week must be between 1 and 7.")
        return
    item["goal_per_week"] = args.per_week
    _touch_item(item)
    _save_items(items)
    print(f"Set goal for habit #{args.id}: {args.per_week}/week.")


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

    sync = sub.add_parser("sync", help="Sync local habits to Postgres")
    sync.set_defaults(func=cmd_sync)

    pull = sub.add_parser("pull", help="Pull habits from Postgres into local store")
    pull.set_defaults(func=cmd_pull)

    week = sub.add_parser("week", help="Weekly goal progress view")
    week.add_argument("--date", help="Override reference date (YYYY-MM-DD)")
    week.add_argument("--week-start", choices=["mon", "tue", "wed", "thu", "fri", "sat", "sun"], default="mon")
    week.add_argument("--all", action="store_true", help="Include completed habits")
    week.set_defaults(func=cmd_week)

    nudge = sub.add_parser("nudge", help="Show habits that need attention")
    nudge.add_argument("--days", type=int, default=3, help="Days since last check-in to flag")
    nudge.add_argument("--date", help="Override reference date (YYYY-MM-DD)")
    nudge.add_argument("--week-start", choices=["mon", "tue", "wed", "thu", "fri", "sat", "sun"], default="mon")
    nudge.add_argument("--all", action="store_true", help="Include completed habits")
    nudge.set_defaults(func=cmd_nudge)

    goal = sub.add_parser("goal", help="Set or clear a weekly goal for a habit")
    goal.add_argument("id", type=int, help="Habit id")
    goal.add_argument("per_week", type=int, nargs="?", default=0, help="Times per week (1-7)")
    goal.add_argument("--clear", action="store_true", help="Clear the goal")
    goal.set_defaults(func=cmd_goal)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
