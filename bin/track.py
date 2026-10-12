#!/usr/bin/env python3
"""Трекер курса: статусы тем, пакеты, чекпоинты, интервальные повторения.

Состояние ученика — state/topics.json (создаёт bin/init_learner.py).
Структура курса — course/topics.json. Статусы меняются только этим скриптом.

Команды:
  validate                         проверить state/topics.json против курса
  status [--mentor]                где я: этапы, активная тема, повторения, отставание
  due                              повторения, срок которых наступил
  start <тема>                     начать тему (status: learning)
  packet-pass <пакет> --protocol F засчитать пакет (все пункты протокола «верно»)
  close <тема> --protocol F [--weak "a; b"]   закрыть тему по протоколу /check
  shaky <тема> [--weak "a; b"]     пометить тему шаткой
  review <тема> --protocol F       записать повторение (протокол определяет итог)
  cp <CPn|CPTn> [--protocol F --artifact ПУТЬ]  статус чекпоинта или сдача
  migrate                          добавить в состояние новые темы и чекпоинты курса
Минимум Python 3.11, без внешних зависимостей.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from courselib import chosen_tracks, route_stages, route_topics, stage_checkpoint, track_ids  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
COURSE = ROOT / "course" / "topics.json"
STATE_DIR = ROOT / "state"
STATE = STATE_DIR / "topics.json"
STATUSES = ("new", "learning", "practiced", "closed", "shaky")
VERDICTS = ("верно", "частично", "неверно")


def today() -> dt.date:
    return dt.date.today()


def load_course() -> dict:
    return json.loads(COURSE.read_text(encoding="utf-8"))


def load_state(allow_missing: bool = False) -> dict:
    if not STATE.exists():
        sys.exit("Нет state/topics.json. Новый ученик: python3 bin/init_learner.py (см. ONBOARDING.md)")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if not allow_missing:
        course = load_course()
        if any(t["id"] not in state["topics"] for t in course["topics"]) or \
                any(c["id"] not in state["checkpoints"] for c in course["checkpoints"]):
            sys.exit("Курс обновился: в состоянии нет новых тем. Сначала ./bin/track.py migrate")
    return state


def save_state(state: dict) -> None:
    state["updated"] = today().isoformat()
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def topic_ids(course: dict) -> list[str]:
    return [t["id"] for t in course["topics"]]


def packet_index(course: dict) -> dict[str, str]:
    return {p["id"]: t["id"] for t in course["topics"] for p in t["packets"]}


def find_topic(course: dict, tid: str) -> dict:
    tid = tid.upper()
    for t in course["topics"]:
        if t["id"] == tid:
            return t
    sys.exit(f"Нет темы {tid}. Темы: {', '.join(topic_ids(course))}")


# ---------- протоколы ----------

def parse_protocol(path: str) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        sys.exit(f"Протокол не найден: {path}")
    try:
        p.resolve().relative_to((STATE_DIR / "checks").resolve())
    except ValueError:
        sys.exit("Протокол должен лежать в state/checks/")
    text = p.read_text(encoding="utf-8")
    head: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^([a-z_]+):\s*(.*)$", line.strip())
        if m:
            head.setdefault(m.group(1), m.group(2).strip())
    items = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0].isdigit():
            verdict = cells[2].lower()
            try:
                points = float(cells[3].replace(",", "."))
            except ValueError:
                sys.exit(f"Пункт {cells[0]}: баллы не число: {cells[3]!r}")
            if verdict not in VERDICTS:
                sys.exit(f"Пункт {cells[0]}: вердикт должен быть одним из {VERDICTS}, а не {cells[2]!r}")
            items.append({"n": int(cells[0]), "task": cells[1], "verdict": verdict, "points": points})
    for key in ("topic", "type", "date", "help"):
        if key not in head:
            sys.exit(f"В протоколе нет строки «{key}: …» (формат — 10-learning-loop.md)")
    if not items:
        sys.exit("В протоколе нет таблицы пунктов «| № | Задание | Вердикт | Баллы |»")
    return {"path": str(p.relative_to(ROOT)), "head": head, "items": items,
            "score": sum(i["points"] for i in items)}


# ---------- команды ----------

def cmd_validate(_: argparse.Namespace) -> int:
    course = load_course()
    state = load_state(allow_missing=True)
    errors = []
    ids = topic_ids(course)
    st_ids = list(state.get("topics", {}).keys())
    for tid in ids:
        if tid not in state.get("topics", {}):
            errors.append(f"в состоянии нет темы {tid}")
    for tid in st_ids:
        if tid not in ids:
            errors.append(f"в состоянии лишняя тема {tid}")
    pidx = packet_index(course)
    for tid, t in state.get("topics", {}).items():
        if t.get("status") not in STATUSES:
            errors.append(f"{tid}: неизвестный статус {t.get('status')!r}")
        for key in ("closed_on", "next_review", "planned_end", "started_on"):
            v = t.get(key)
            if v:
                try:
                    dt.date.fromisoformat(v)
                except ValueError:
                    errors.append(f"{tid}.{key}: не дата {v!r}")
        for pid in t.get("packets_passed", []):
            if pidx.get(pid) != tid:
                errors.append(f"{tid}: пакет {pid} не из этой темы")
        if t.get("status") == "closed" and not t.get("close_protocol"):
            errors.append(f"{tid}: закрыта без протокола")
    for cp in course["checkpoints"]:
        if cp["id"] not in state.get("checkpoints", {}):
            errors.append(f"в состоянии нет чекпоинта {cp['id']}")
    cfg = STATE_DIR / "config.json"
    if cfg.exists():
        bad = [x for x in json.loads(cfg.read_text(encoding="utf-8")).get("tracks", []) if x not in track_ids(course)]
        if bad:
            errors.append(f"config.json: неизвестные треки {bad}; есть {track_ids(course)}")
    if errors:
        if any(e.startswith("в состоянии нет") for e in errors):
            errors.append("курс обновился — добавить новое: ./bin/track.py migrate")
        print("ОШИБКИ:\n- " + "\n- ".join(errors))
        return 1
    print(f"OK: {len(ids)} тем, {len(course['checkpoints'])} чекпоинтов")
    return 0


def due_list(state: dict) -> list[tuple[str, str]]:
    out = []
    for tid, t in state["topics"].items():
        nr = t.get("next_review")
        if nr and dt.date.fromisoformat(nr) <= today() and t.get("status") in ("closed", "shaky"):
            out.append((tid, nr))
    return sorted(out, key=lambda x: x[1])


def cmd_status(a: argparse.Namespace) -> int:
    course = load_course()
    state = load_state()
    print(f"Сегодня {today().isoformat()}")
    tracks = chosen_tracks(course)
    for s in route_stages(course, tracks):
        if s["id"] == "S0":
            continue
        ts = [t for t in course["topics"] if t["stage"] == s["id"]]
        closed = sum(1 for t in ts if state["topics"].get(t["id"], {}).get("status") == "closed")
        cp_id = stage_checkpoint(course, s["id"])
        cp = state["checkpoints"].get(cp_id, {})
        mark = "пройден" if cp.get("passed_on") else "не пройден"
        name = f"Этап {s['n']}" if s.get("kind", "core") == "core" else f"Трек {s['id']}"
        print(f"  {name}. {s['title']}: закрыто тем {closed}/{len(ts)}; {cp_id} {mark}")
    rest = [x for x in track_ids(course) if x not in tracks]
    if rest:
        print("Треки не выбраны: " + ", ".join(rest) + " (выбор — bin/plan.py tracks)")
    active = [tid for tid, t in state["topics"].items() if t["status"] in ("learning", "practiced")]
    shaky = [tid for tid, t in state["topics"].items() if t["status"] == "shaky"]
    print("Активные темы: " + (", ".join(active) if active else "нет"))
    if shaky:
        print("Шаткие темы: " + ", ".join(shaky))
    due = due_list(state)
    print("Повторения сегодня: " + (", ".join(f"{t} (с {d})" for t, d in due) if due else "нет"))
    behind = []
    for tid, t in state["topics"].items():
        pe = t.get("planned_end")
        if pe and t["status"] != "closed" and dt.date.fromisoformat(pe) < today():
            behind.append(f"{tid} (план {pe})")
    if behind:
        print("Позади плана: " + ", ".join(behind))
    nxt = next((t["id"] for t in route_topics(course, tracks)
                if state["topics"].get(t["id"], {}).get("status") == "new"), None)
    print("Следующая новая тема: " + (nxt or "все начаты"))
    if a.mentor:
        for tid, t in state["topics"].items():
            if t["status"] != "new":
                print(f"  [mentor] {tid}: {t['status']}, пакеты {t.get('packets_passed', [])}, "
                      f"слабые {t.get('weak', [])}, ступень {t.get('review_step')}, след. {t.get('next_review')}")
    return 0


def cmd_due(_: argparse.Namespace) -> int:
    state = load_state()
    due = due_list(state)
    if not due:
        print("Повторений на сегодня нет")
    for tid, d in due:
        t = state["topics"][tid]
        print(f"{tid}: срок {d}; слабые места: {'; '.join(t.get('weak', [])) or '—'}")
    return 0


def cmd_start(a: argparse.Namespace) -> int:
    course = load_course()
    t = find_topic(course, a.topic)
    state = load_state()
    st = state["topics"][t["id"]]
    if st["status"] == "closed":
        sys.exit(f"{t['id']} уже закрыта; для работы над ней — /review")
    st["status"] = "learning"
    st.setdefault("started_on", today().isoformat())
    save_state(state)
    print(f"{t['id']} «{t['title']}»: в работе")
    return 0


def cmd_packet_pass(a: argparse.Namespace) -> int:
    course = load_course()
    pidx = packet_index(course)
    pid = a.packet.upper()
    if pid not in pidx:
        sys.exit(f"Нет пакета {pid}")
    proto = parse_protocol(a.protocol)
    if proto["head"]["topic"].upper() not in (pid, pidx[pid]):
        sys.exit("Протокол относится к другому пакету/теме")
    bad = [i["n"] for i in proto["items"] if i["verdict"] != "верно"]
    if bad:
        sys.exit(f"Пакет не засчитан: пункты {bad} не «верно». Разобрать и исправить.")
    state = load_state()
    st = state["topics"][pidx[pid]]
    if pid not in st.setdefault("packets_passed", []):
        st["packets_passed"].append(pid)
    if st["status"] == "new":
        st["status"] = "learning"
        st["started_on"] = today().isoformat()
    all_p = [p["id"] for p in find_topic(course, pidx[pid])["packets"]]
    if all(p in st["packets_passed"] for p in all_p) and st["status"] == "learning":
        st["status"] = "practiced"
    st.setdefault("protocols", []).append(proto["path"])
    save_state(state)
    print(f"Пакет {pid} засчитан. Тема {pidx[pid]}: {st['status']}")
    return 0


def split_weak(s: str | None) -> list[str]:
    return [w.strip() for w in (s or "").split(";") if w.strip()]


def cmd_close(a: argparse.Namespace) -> int:
    course = load_course()
    t = find_topic(course, a.topic)
    state = load_state()
    st = state["topics"][t["id"]]
    missing = [p["id"] for p in t["packets"] if p["id"] not in st.get("packets_passed", [])]
    if missing:
        sys.exit(f"Нельзя закрыть {t['id']}: не пройдены пакеты {missing}")
    proto = parse_protocol(a.protocol)
    h = proto["head"]
    if h["topic"].upper() != t["id"] or h["type"] != "check":
        sys.exit("Нужен протокол /check этой темы (topic: <тема>, type: check)")
    if h["help"] not in ("none", "docs"):
        sys.exit("Проверка с подсказками ментора не засчитывается как независимая (help: none|docs)")
    if len(proto["items"]) < 5:
        sys.exit("В проверке должно быть 5 заданий")
    if proto["score"] > 10:
        sys.exit("Сумма баллов больше 10 — протокол неверен")
    st.setdefault("protocols", []).append(proto["path"])
    weak = split_weak(a.weak) or split_weak(h.get("weak"))
    if proto["score"] < course["close_threshold"]:
        st["status"] = "shaky"
        st["weak"] = weak
        st["next_review"] = (today() + dt.timedelta(days=3)).isoformat()
        save_state(state)
        print(f"{t['id']}: не закрыта, тема шаткая. Повторная проверка — после работы над слабыми местами")
        return 0
    st.update(status="closed", closed_on=today().isoformat(), close_protocol=proto["path"],
              weak=weak, review_step=0,
              next_review=(today() + dt.timedelta(days=course["review_intervals_days"][0])).isoformat())
    save_state(state)
    print(f"{t['id']}: закрыта. Первое повторение {st['next_review']}")
    return 0


def cmd_shaky(a: argparse.Namespace) -> int:
    course = load_course()
    t = find_topic(course, a.topic)
    state = load_state()
    st = state["topics"][t["id"]]
    st["status"] = "shaky"
    st["weak"] = sorted(set(st.get("weak", []) + split_weak(a.weak)))
    st["next_review"] = (today() + dt.timedelta(days=3)).isoformat()
    save_state(state)
    print(f"{t['id']}: шаткая; слабые места: {'; '.join(st['weak']) or '—'}")
    return 0


def cmd_review(a: argparse.Namespace) -> int:
    course = load_course()
    t = find_topic(course, a.topic)
    state = load_state()
    st = state["topics"][t["id"]]
    if st["status"] not in ("closed", "shaky"):
        sys.exit("Повторяются только закрытые или шаткие темы")
    proto = parse_protocol(a.protocol)
    if proto["head"]["topic"].upper() != t["id"] or proto["head"]["type"] != "review":
        sys.exit("Нужен протокол повторения этой темы (type: review)")
    st.setdefault("protocols", []).append(proto["path"])
    right = sum(1 for i in proto["items"] if i["verdict"] == "верно")
    ok = right / len(proto["items"]) >= 0.8
    intervals = course["review_intervals_days"]
    if ok and st["status"] == "closed":
        step = st.get("review_step", 0) + 1
        st["review_step"] = step
        if step >= len(intervals):
            st["next_review"] = None
            msg = "цикл повторений завершён"
        else:
            st["next_review"] = (today() + dt.timedelta(days=intervals[step])).isoformat()
            msg = f"следующее повторение {st['next_review']}"
    else:
        st["status"] = "shaky"
        st["review_step"] = 0
        st["weak"] = sorted(set(st.get("weak", []) + split_weak(proto["head"].get("weak"))))
        st["next_review"] = (today() + dt.timedelta(days=3)).isoformat()
        msg = "тема шаткая: проработать слабые места и пройти /check заново"
    save_state(state)
    print(f"{t['id']}: {msg}")
    return 0


def cmd_cp(a: argparse.Namespace) -> int:
    course = load_course()
    cp_id = a.cp.upper()
    cp = next((c for c in course["checkpoints"] if c["id"] == cp_id), None)
    if not cp:
        sys.exit("Чекпоинты: " + ", ".join(c["id"] for c in course["checkpoints"]))
    state = load_state()
    ts = [t["id"] for t in course["topics"] if t["stage"] == cp["stage"]]
    open_ts = [tid for tid in ts if state["topics"][tid]["status"] != "closed"]
    rec = state["checkpoints"][cp_id]
    if not a.protocol:
        print(f"{cp_id}: {'пройден ' + rec['passed_on'] if rec.get('passed_on') else 'не пройден'}")
        print("Не закрыты темы: " + (", ".join(open_ts) if open_ts else "все закрыты — можно сдавать"))
        return 0
    if open_ts:
        sys.exit(f"Сдавать рано: не закрыты {open_ts}")
    if not a.artifact:
        sys.exit("Чекпоинт не сдаётся без артефакта: --artifact ПУТЬ")
    proto = parse_protocol(a.protocol)
    if proto["head"]["topic"].upper() != cp_id or proto["head"]["type"] != "checkpoint":
        sys.exit("Нужен протокол чекпоинта (topic: CPn, type: checkpoint)")
    if proto["score"] < course["close_threshold"]:
        rec.setdefault("attempts", []).append(proto["path"])
        save_state(state)
        print(f"{cp_id}: не пройден. Доработать по протоколу и сдать снова")
        return 0
    rec.update(passed_on=today().isoformat(), protocol=proto["path"], artifact=a.artifact)
    save_state(state)
    print(f"{cp_id}: пройден")
    return 0


def cmd_migrate(_: argparse.Namespace) -> int:
    course = load_course()
    state = load_state(allow_missing=True)
    added = []
    for t in course["topics"]:
        if t["id"] not in state["topics"]:
            state["topics"][t["id"]] = {"status": "new", "packets_passed": [], "weak": [],
                                        "planned_end": None, "next_review": None}
            added.append(t["id"])
    for c in course["checkpoints"]:
        if c["id"] not in state["checkpoints"]:
            state["checkpoints"][c["id"]] = {"passed_on": None}
            added.append(c["id"])
    extra = [tid for tid in state["topics"] if tid not in topic_ids(course)]
    state["course_version"] = course["version"]
    save_state(state)
    print("Добавлено: " + (", ".join(added) if added else "ничего — состояние актуально"))
    if extra:
        print("В состоянии есть темы, которых нет в курсе (не удалены): " + ", ".join(extra))
    cfg = STATE_DIR / "config.json"
    if cfg.exists():
        c = json.loads(cfg.read_text(encoding="utf-8"))
        if "tracks" not in c:
            c["tracks"] = []
            cfg.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print("В config.json добавлен пустой список треков: выбрать — bin/plan.py tracks")
    print("Сроки новых тем не назначены: bin/plan.py forecast → согласовать → apply --yes")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate").set_defaults(f=cmd_validate)
    p = sub.add_parser("status"); p.add_argument("--mentor", action="store_true"); p.set_defaults(f=cmd_status)
    sub.add_parser("due").set_defaults(f=cmd_due)
    p = sub.add_parser("start"); p.add_argument("topic"); p.set_defaults(f=cmd_start)
    p = sub.add_parser("packet-pass"); p.add_argument("packet"); p.add_argument("--protocol", required=True); p.set_defaults(f=cmd_packet_pass)
    p = sub.add_parser("close"); p.add_argument("topic"); p.add_argument("--protocol", required=True); p.add_argument("--weak"); p.set_defaults(f=cmd_close)
    p = sub.add_parser("shaky"); p.add_argument("topic"); p.add_argument("--weak"); p.set_defaults(f=cmd_shaky)
    p = sub.add_parser("review"); p.add_argument("topic"); p.add_argument("--protocol", required=True); p.set_defaults(f=cmd_review)
    sub.add_parser("migrate").set_defaults(f=cmd_migrate)
    p = sub.add_parser("cp"); p.add_argument("cp"); p.add_argument("--protocol"); p.add_argument("--artifact"); p.set_defaults(f=cmd_cp)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
