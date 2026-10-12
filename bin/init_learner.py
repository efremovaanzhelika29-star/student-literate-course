#!/usr/bin/env python3
"""Создать state/ нового ученика из templates/state/.

  python3 bin/init_learner.py --hours 9 [--git]

Существующее состояние не перезаписывается никогда.
--git делает state/ отдельным git-репозиторием (история прогресса не теряется).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "state"
STATE = ROOT / "state"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=9, help="примерный бюджет, ч/нед (для профиля)")
    ap.add_argument("--git", action="store_true", help="сделать state/ отдельным git-репозиторием")
    a = ap.parse_args()

    if sys.version_info < (3, 11):
        sys.exit("Нужен Python 3.11 или новее")
    if STATE.exists() and any(STATE.iterdir()):
        sys.exit("state/ уже существует — ничего не меняю. Продолжайте учёбу: откройте агента и напишите «начнём».")

    start = dt.date.today().isoformat()
    shutil.copytree(TEMPLATES, STATE, dirs_exist_ok=True)
    for p in STATE.rglob("*"):
        if p.is_file() and p.suffix in (".md", ".json"):
            t = p.read_text(encoding="utf-8")
            t = t.replace("{START}", start).replace("{HOURS}", f"{a.hours:g}")
            p.write_text(t, encoding="utf-8")

    course = json.loads((ROOT / "course" / "topics.json").read_text(encoding="utf-8"))
    state = {
        "course_version": course["version"],
        "created": start,
        "updated": start,
        "topics": {t["id"]: {"status": "new", "packets_passed": [], "weak": [],
                             "planned_end": None, "next_review": None} for t in course["topics"]},
        "checkpoints": {c["id"]: {"passed_on": None} for c in course["checkpoints"]},
    }
    (STATE / "topics.json").write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    if a.git:
        subprocess.run(["git", "init", "-q"], cwd=STATE, check=True)
        subprocess.run(["git", "add", "-A"], cwd=STATE, check=True)
        subprocess.run(["git", "-c", "user.name=learner", "-c", "user.email=learner@localhost",
                        "commit", "-qm", "Старт курса"], cwd=STATE, check=False)

    print(f"Создано state/ ({len(course['topics'])} тем, {len(course['checkpoints'])} чекпоинтов).")
    print("Дальше: откройте Claude Code или Codex в корне курса и напишите «начнём» — агент проведёт онбординг.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
