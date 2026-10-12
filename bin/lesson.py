#!/usr/bin/env python3
"""Указатель текущего шага урока (state/lesson.json).

  python3 bin/lesson.py context     короткий контекст для продолжения (без сети)
  python3 bin/lesson.py validate    проверить lesson.json
  python3 bin/lesson.py set --ref T04-P1 --mode learn --step "…" [--pending "…"] [--await-fix "ошибка 1; ошибка 2"]

Указатель обновляют на границе учебного блока, при паузе и завершении урока.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
LESSON = STATE / "lesson.json"
MODES = ("onboarding", "learn", "practice", "check", "review", "mock", "status", "pause")
REF_RE = re.compile(r"^(ONBOARDING|T\d{2}(-P\d)?|CP[1-6]|MOCK)$")


def load() -> dict:
    if not LESSON.exists():
        sys.exit("Нет state/lesson.json. Новый ученик: python3 bin/init_learner.py")
    return json.loads(LESSON.read_text(encoding="utf-8"))


def errors_of(d: dict) -> list[str]:
    errs = []
    for k in ("task_reference", "mode", "step", "pending", "await_fix", "updated"):
        if k not in d:
            errs.append(f"нет поля {k}")
    if errs:
        return errs
    if not REF_RE.match(str(d["task_reference"])):
        errs.append(f"task_reference {d['task_reference']!r}: ожидается ONBOARDING, Tnn, Tnn-Pn, CPn или MOCK")
    if d["mode"] not in MODES:
        errs.append(f"mode {d['mode']!r}: ожидается одно из {MODES}")
    if not isinstance(d["await_fix"], list):
        errs.append("await_fix должен быть списком")
    if not str(d["step"]).strip():
        errs.append("step пуст — указатель должен называть следующий конкретный шаг")
    try:
        dt.date.fromisoformat(d["updated"])
    except (TypeError, ValueError):
        errs.append(f"updated не дата: {d['updated']!r}")
    return errs


def cmd_validate(_: argparse.Namespace) -> int:
    errs = errors_of(load())
    if errs:
        print("ОШИБКИ lesson.json:\n- " + "\n- ".join(errs))
        return 1
    print("OK: lesson.json")
    return 0


def cmd_context(_: argparse.Namespace) -> int:
    d = load()
    print(f"Текущее: {d['task_reference']} · режим {d['mode']} · обновлено {d['updated']}")
    print(f"Шаг: {d['step']}")
    if d.get("pending"):
        print(f"Ожидаемый ответ/вопрос: {d['pending']}")
    if d.get("await_fix"):
        print("Ошибки к исправлению (по одной): " + "; ".join(d["await_fix"]))
    sessions = sorted((STATE / "sessions").glob("*.md"))
    if sessions:
        last = sessions[-1]
        lines = [l for l in last.read_text(encoding="utf-8").splitlines() if l.strip()][:12]
        print(f"Последняя сессия ({last.name}):")
        print("  " + "\n  ".join(lines))
    if d["task_reference"] == "ONBOARDING":
        print("Онбординг не завершён: провести его по mentoring/harness.md до любой темы.")
    errs = errors_of(d)
    if errs:
        print("Внимание: lesson.json невалиден — " + "; ".join(errs))
    return 0


def cmd_set(a: argparse.Namespace) -> int:
    d = load()
    d["task_reference"] = a.ref.upper()
    d["mode"] = a.mode
    d["step"] = a.step
    d["pending"] = a.pending or ""
    d["await_fix"] = [x.strip() for x in (a.await_fix or "").split(";") if x.strip()]
    d["updated"] = dt.date.today().isoformat()
    errs = errors_of(d)
    if errs:
        sys.exit("Не сохранено:\n- " + "\n- ".join(errs))
    LESSON.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Указатель сохранён")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("context").set_defaults(f=cmd_context)
    sub.add_parser("validate").set_defaults(f=cmd_validate)
    p = sub.add_parser("set")
    p.add_argument("--ref", required=True)
    p.add_argument("--mode", required=True, choices=MODES)
    p.add_argument("--step", required=True)
    p.add_argument("--pending")
    p.add_argument("--await-fix")
    p.set_defaults(f=cmd_set)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
