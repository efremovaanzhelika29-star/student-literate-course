#!/usr/bin/env python3
"""Расписание ученицы и прогноз сроков курса (mentoring/planning.md).

  python3 bin/plan.py set --start 2026-10-19 --mon 60 --wed 90 --sat 180 [--break 2026-12-30:2027-01-08]
  python3 bin/plan.py forecast            прогноз: окончание этапов и курса по расписанию
  python3 bin/plan.py apply --yes         записать согласованные даты тем в state/topics.json

Даты — ориентиры. Пропущенное занятие не создаёт долг: сдвиг фиксируется в
state/progress.md, после чего прогноз пересчитывается и заново согласуется.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
CONFIG = STATE / "config.json"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def load(p: Path) -> dict:
    if not p.exists():
        sys.exit(f"Нет {p.relative_to(ROOT)}. Новый ученик: python3 bin/init_learner.py")
    return json.loads(p.read_text(encoding="utf-8"))


def dump(p: Path, d: dict) -> None:
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def forecast(cfg: dict, course: dict) -> tuple[list[tuple[str, str, float, dt.date]], float]:
    sch = cfg["schedule"]
    weekly = sch["weekly_minutes"]
    per_week = sum(weekly.values())
    if per_week <= 0 or not sch.get("start"):
        sys.exit("Расписание не задано: python3 bin/plan.py set --start ГГГГ-ММ-ДД --mon 60 …")
    breaks = [(dt.date.fromisoformat(a), dt.date.fromisoformat(b)) for a, b in sch.get("breaks", [])]
    day = dt.date.fromisoformat(sch["start"]) - dt.timedelta(days=1)
    items = [("S0", "Старт и аудит", 6.0)] + [(t["id"], t["title"], float(t["hours"])) for t in course["topics"]]
    out = []
    pool = 0.0
    for tid, title, hours in items:
        need = hours * 60
        while pool < need:
            day += dt.timedelta(days=1)
            if not any(x <= day <= y for x, y in breaks):
                pool += weekly[DAYS[day.weekday()]]
        pool -= need
        out.append((tid, title, hours, day))
    return out, per_week / 60


def cmd_set(a: argparse.Namespace) -> int:
    cfg = load(CONFIG)
    sch = cfg["schedule"]
    if a.start:
        dt.date.fromisoformat(a.start)
        sch["start"] = a.start
    for d in DAYS:
        v = getattr(a, d)
        if v is not None:
            sch["weekly_minutes"][d] = v
    for b in a.breaks or []:
        x, y = b.split(":")
        dt.date.fromisoformat(x), dt.date.fromisoformat(y)
        sch.setdefault("breaks", []).append([x, y])
    sch["agreed"] = False
    dump(CONFIG, cfg)
    print(f"Расписание сохранено: {sum(sch['weekly_minutes'].values())} мин/нед. Дальше: plan.py forecast")
    return 0


def cmd_forecast(_: argparse.Namespace) -> int:
    cfg = load(CONFIG)
    course = json.loads((ROOT / "course" / "topics.json").read_text(encoding="utf-8"))
    rows, hpw = forecast(cfg, course)
    total = sum(r[2] for r in rows)
    end = rows[-1][3]
    start = dt.date.fromisoformat(cfg["schedule"]["start"])
    weeks = (end - start).days / 7
    print(f"Бюджет {hpw:.1f} ч/нед; курс {total:.0f} ч; окончание ≈ {end.isoformat()} (~{weeks:.0f} нед.)")
    stage_end: dict[str, dt.date] = {}
    tstage = {t["id"]: t["stage"] for t in course["topics"]}
    for tid, _, _, d in rows:
        stage_end[tstage.get(tid, "S0")] = d
    for s in course["stages"]:
        print(f"  Этап {s['n']}. {s['title']}: до {stage_end[s['id']].isoformat()}")
    print("Даты не применены. После согласования: python3 bin/plan.py apply --yes")
    return 0


def cmd_apply(a: argparse.Namespace) -> int:
    if not a.yes:
        sys.exit("Применяются только согласованные с ученицей даты: добавьте --yes")
    cfg = load(CONFIG)
    state = load(STATE / "topics.json")
    course = json.loads((ROOT / "course" / "topics.json").read_text(encoding="utf-8"))
    rows, _ = forecast(cfg, course)
    for tid, _, _, d in rows:
        if tid in state["topics"]:
            state["topics"][tid]["planned_end"] = d.isoformat()
    cfg["schedule"]["agreed"] = True
    dump(STATE / "topics.json", state)
    dump(CONFIG, cfg)
    print(f"Даты записаны. Окончание курса ≈ {rows[-1][3].isoformat()}. Отметьте это в state/progress.md")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("set")
    p.add_argument("--start")
    for d in DAYS:
        p.add_argument(f"--{d}", type=int)
    p.add_argument("--break", dest="breaks", action="append", help="ГГГГ-ММ-ДД:ГГГГ-ММ-ДД")
    p.set_defaults(f=cmd_set)
    sub.add_parser("forecast").set_defaults(f=cmd_forecast)
    p = sub.add_parser("apply")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(f=cmd_apply)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
