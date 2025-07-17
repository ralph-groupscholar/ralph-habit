# ralph-habit

A tiny, local-first habit tracker for the terminal.

## Usage

```bash
python habit.py add "Drink water"
python habit.py list
python habit.py checkin 1
python habit.py checkin 1 --date 2026-02-07
python habit.py checkin 1 --start 2026-02-01 --end 2026-02-07
python habit.py uncheck 1 --date 2026-02-05
python habit.py uncheck 1 --start 2026-02-01 --end 2026-02-03
python habit.py streak 1
python habit.py done 1
python habit.py list --all
python habit.py rename 1 "Drink more water"
python habit.py stats
python habit.py report
python habit.py report --days 14
python habit.py report --date 2026-02-07 --all
python habit.py history 1
python habit.py history 1 --days 30
python habit.py history 1 --date 2026-02-07
python habit.py goal 1 5
python habit.py goal 1 --clear
```

Data lives in `~/.ralph-habit.json`.
