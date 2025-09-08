# ralph-habit

A tiny, local-first habit tracker for the terminal.

## Usage

```bash
python habit.py add "Drink water"
python habit.py list
python habit.py checkin 1
python habit.py checkin 1 --date 2026-02-07
python habit.py checkin 1 --start 2026-02-01 --end 2026-02-07
python habit.py checkin-all
python habit.py checkin-all --date 2026-02-07
python habit.py checkin-all --start 2026-02-01 --end 2026-02-07 --include-unscheduled
python habit.py uncheck 1 --date 2026-02-05
python habit.py uncheck 1 --start 2026-02-01 --end 2026-02-03
python habit.py streak 1
python habit.py done 1
python habit.py reopen 1
python habit.py list --all
python habit.py rename 1 "Drink more water"
python habit.py stats
python habit.py report
python habit.py report --days 14
python habit.py report --date 2026-02-07 --all
python habit.py history 1
python habit.py history 1 --days 30
python habit.py history 1 --date 2026-02-07
python habit.py today
python habit.py today --week-start sun
python habit.py today --date 2026-02-07 --all
python habit.py week
python habit.py week --week-start sun
python habit.py week --date 2026-02-07 --all
python habit.py nudge
python habit.py nudge --days 2
python habit.py nudge --week-start sun --date 2026-02-07
python habit.py review
python habit.py review --days 21 --stale-days 5
python habit.py review --date 2026-02-07 --week-start sun --all
python habit.py coverage
python habit.py coverage --days 21 --limit 6
python habit.py coverage --date 2026-02-07 --all
python habit.py timeline
python habit.py timeline --days 10 --limit 5
python habit.py timeline --date 2026-02-07 --all
python habit.py plan
python habit.py plan --days 10
python habit.py plan --date 2026-02-07 --limit 6 --all
python habit.py momentum
python habit.py momentum --windows 14,30 --date 2026-02-07 --all
python habit.py weekday
python habit.py weekday --days 21 --date 2026-02-07 --all
python habit.py goal 1 5
python habit.py goal 1 --clear
python habit.py schedule 1 mon wed fri
python habit.py schedule 1
python habit.py schedule 1 --clear
python habit.py note 1 "Focus on weekdays"
python habit.py note 1 --clear
python habit.py month 1
python habit.py month 1 --month 2026-02
python habit.py month 1 --date 2026-02-07 --week-start sun
python habit.py export
python habit.py export ~/habits.csv
python habit.py import ~/habits.csv
python habit.py import ~/habits.csv --update
python habit.py sync
python habit.py pull
```

Data lives in `~/.ralph-habit.json`.

## Postgres Sync (Optional)

To sync to a Postgres database, set `DATABASE_URL` or `RALPH_HABIT_DB_URL` and install
`psycopg`:

```bash
pip install "psycopg[binary]"
```

Use `RALPH_HABIT_PROFILE` to keep multiple devices separate (defaults to `default`).
Weekly goals, notes, and schedules are included in sync/pull operations.
