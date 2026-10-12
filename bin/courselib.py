"""Общие функции курса: ядро, выбранные треки, порядок тем (маршрут).

Ядро — этапы с kind "core" (S0–S6). Треки — этапы с kind "track" (TR1–TR7);
ученица выбирает их в state/config.json → "tracks". Трек идёт в маршруте
сразу после этапа, указанного в его "after".
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COURSE = ROOT / "course" / "topics.json"
CONFIG = ROOT / "state" / "config.json"


def load_course() -> dict:
    return json.loads(COURSE.read_text(encoding="utf-8"))


def track_ids(course: dict) -> list[str]:
    return [s["id"] for s in course["stages"] if s.get("kind") == "track"]


def chosen_tracks(course: dict) -> list[str]:
    if not CONFIG.exists():
        return []
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    valid = set(track_ids(course))
    return [t for t in cfg.get("tracks", []) if t in valid]


def stage_checkpoint(course: dict, stage_id: str) -> str | None:
    return next((c["id"] for c in course["checkpoints"] if c["stage"] == stage_id), None)


def route_stages(course: dict, tracks: list[str] | None = None) -> list[dict]:
    """Этапы в порядке прохождения: ядро, после каждого этапа — его выбранные треки."""
    if tracks is None:
        tracks = chosen_tracks(course)
    core = [s for s in course["stages"] if s.get("kind", "core") == "core"]
    tr = [s for s in course["stages"] if s.get("kind") == "track" and s["id"] in tracks]
    out = []
    for s in core:
        out.append(s)
        out += [t for t in tr if t.get("after") == s["id"]]
    return out


def route_topics(course: dict, tracks: list[str] | None = None) -> list[dict]:
    order = [s["id"] for s in route_stages(course, tracks)]
    return [t for sid in order for t in course["topics"] if t["stage"] == sid]
