#!/usr/bin/env python3
"""Файлы практики пакетов: practice/<пакет>/.

  python3 bin/practice.py init T04-P1 [--questions 6]       шаблон answer.md
  python3 bin/practice.py init T04-P2                        шаблон карты разбора map.md
  python3 bin/practice.py init T04-P3                        план этюда answer.md
  python3 bin/practice.py init T04-P3 --practice --stage 1   этап этюда t1_stage1.md
  python3 bin/practice.py run T04-P3                         формальная проверка файлов

`run` проверяет только форму: заполненность, объём, отличие второго варианта.
Содержание оценивает ментор. Существующие файлы ученицы не перезаписываются.
practice/ исключена из git курса (.gitignore и .git/info/exclude).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRACTICE = ROOT / "practice"

MAP_ITEMS = [
    "Драматический вопрос (одной фразой); где поставлен и где закрыт",
    "Герой: желание / потребность / рана-ложь; антагонистическая сила",
    "Конфликт по уровням: внутренний / межличностный / внеличностный",
    "Узлы: инцидент — первый поворот — середина — кризис — кульминация — развязка; модель структуры",
    "Управление информацией: тайна / напряжение / ирония — где и как",
    "Рассказчик: кто, из какого времени; что сломалось бы при другом",
    "Ключевая сцена: заряд (+/−) в начале и в конце; биты; что переворачивает",
    "Подготовки и окупаемости (3 пары)",
    "Лейтмотивы",
    "Финал: тип; что делает последняя фраза",
    "Что украсть (2–3 приёма — инструкцией себе)",
    "Ошибка подражателя",
    "Мой текст: какой этюд я напишу по этому приёму",
]


def exclude_practice() -> None:
    excl = ROOT / ".git" / "info" / "exclude"
    if excl.parent.exists():
        cur = excl.read_text(encoding="utf-8") if excl.exists() else ""
        if "practice/" not in cur.split():
            excl.write_text(cur + ("\n" if cur and not cur.endswith("\n") else "") + "practice/\n", encoding="utf-8")


def packet(pid: str) -> tuple[dict, dict]:
    course = json.loads((ROOT / "course" / "topics.json").read_text(encoding="utf-8"))
    for t in course["topics"]:
        for p in t["packets"]:
            if p["id"] == pid.upper():
                return t, p
    sys.exit(f"Нет пакета {pid}")


def write_new(path: Path, text: str) -> None:
    if path.exists():
        print(f"Уже есть, не трогаю: {path.relative_to(ROOT)}")
        return
    path.write_text(text, encoding="utf-8")
    print(f"Создан: {path.relative_to(ROOT)}")


def cmd_init(a: argparse.Namespace) -> int:
    t, p = packet(a.packet)
    d = PRACTICE / p["id"]
    d.mkdir(parents=True, exist_ok=True)
    exclude_practice()
    src = "\n".join(f"- `{s}`" for s in t["sources"])
    head = f"# {p['id']} — {p['title']}\n\nТема {t['id']}: {t['title']}\n\nИсточники:\n{src}\n"
    if a.practice:
        if p["kind"] != "etude":
            sys.exit("Этапы практики есть только у пакета этюда (Pn с kind=etude)")
        n = a.stage
        if n == 1:
            body = (f"{head}\n## Этап 1 — черновик\n\nЗадание: {p['task']}\n\n"
                    "## Приём, который я применяю (инструкцией себе)\n\n\n## Мой текст\n\n")
        else:
            body = (f"{head}\n## Этап {n} — следующий вариант\n\n"
                    "## Правки ментора, которые я учла\n\n\n## Мой текст\n\n\n## Что изменено и почему\n\n")
        write_new(d / f"t1_stage{n}.md", body)
        return 0
    if p["kind"] == "map":
        items = "\n\n".join(f"{i}. **{x}:**\n" for i, x in enumerate(MAP_ITEMS, 1))
        write_new(d / "map.md", f"{head}\nПроизведение: {p.get('works', '—')}\n\n"
                  "Заполните **до** чтения эталонного разбора. Механика, а не пересказ.\n\n" + items + "\n")
        return 0
    if p["kind"] == "etude":
        write_new(d / "answer.md", f"{head}\nЗадание: {p['task']}\n\n"
                  "## План этюда (до письма)\n\n1. Драматический вопрос:\n\n2. Желание героя / что мешает:\n\n"
                  "3. Поворот:\n\n4. Финал (последняя фраза — образ, не вывод):\n\n5. Приём-источник:\n")
        return 0
    qs = "\n".join(f"## Вопрос {i}\n\nОтвет:\n\n" for i in range(1, a.questions + 1))
    if p.get("works"):
        head += f"\nМатериал: {p['works']}\n"
    write_new(d / "answer.md", f"{head}\nВопросы ментор выдаёт в чате. Отвечайте под номерами одним заходом. "
              "Прогноз (если просят) пишите до чтения продолжения.\n\n" + qs)
    return 0


def section(text: str, title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def volume_range(task: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)\s*тыс", task)
    if m:
        return int(m.group(1)) * 1000, int(m.group(2)) * 1000
    m = re.search(r"(\d+)\s*тыс", task)
    if m:
        v = int(m.group(1)) * 1000
        return int(v * 0.8), int(v * 1.2)
    return None


def cmd_run(a: argparse.Namespace) -> int:
    t, p = packet(a.packet)
    d = PRACTICE / p["id"]
    if not d.exists():
        sys.exit(f"Нет {d.relative_to(ROOT)} — сначала: python3 bin/practice.py init {p['id']}")
    problems: list[str] = []
    notes: list[str] = []
    ans = d / "answer.md"
    if ans.exists() and p["kind"] in ("theory",):
        text = ans.read_text(encoding="utf-8")
        for m in re.finditer(r"^## Вопрос (\d+)\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M):
            body = m.group(2).replace("Ответ:", "").strip()
            if len(body) < 40:
                problems.append(f"Вопрос {m.group(1)}: ответа нет или он слишком короткий")
    mp = d / "map.md"
    if p["kind"] == "map":
        if not mp.exists():
            problems.append("нет map.md")
        else:
            text = mp.read_text(encoding="utf-8")
            for i in range(1, len(MAP_ITEMS) + 1):
                m = re.search(rf"^{i}\. \*\*[^*]+\*\*(.*?)(?=^\d+\. \*\*|\Z)", text, re.S | re.M)
                if not m or len(m.group(1).strip()) < 30:
                    problems.append(f"Карта, пункт {i}: пусто или слишком коротко")
            m7 = re.search(r"^7\. \*\*[^*]+\*\*(.*?)(?=^8\. )", text, re.S | re.M)
            if m7 and not re.search(r"[+−-]", m7.group(1)):
                notes.append("Пункт 7: не указан заряд сцены (+/−)")
    if p["kind"] == "etude":
        stages = sorted(d.glob("t1_stage*.md"))
        if not stages:
            problems.append("нет этапов этюда: python3 bin/practice.py init "
                            f"{p['id']} --practice --stage 1")
        rng = volume_range(p.get("task", ""))
        prev = None
        for s in stages:
            text = s.read_text(encoding="utf-8")
            body = section(text, "Мой текст")
            n = len(body)
            label = s.name
            if not body:
                problems.append(f"{label}: раздел «Мой текст» пуст")
            elif rng:
                lo, hi = int(rng[0] * 0.85), int(rng[1] * 1.15)
                if not lo <= n <= hi:
                    problems.append(f"{label}: {n} зн., ожидается {rng[0]}–{rng[1]} (допуск ±15 %)")
                else:
                    notes.append(f"{label}: {n} зн. — в объёме")
            if s.name != "t1_stage1.md":
                if not section(text, "Что изменено и почему"):
                    problems.append(f"{label}: не заполнено «Что изменено и почему»")
                if prev is not None and body:
                    ratio = difflib.SequenceMatcher(None, prev, body).ratio()
                    if ratio > 0.9:
                        problems.append(f"{label}: текст почти не изменился (совпадение {ratio:.0%}) — это не новый вариант")
            elif not section(text, "Приём, который я применяю"):
                problems.append(f"{label}: не сформулирован приём")
            prev = body
    for n in notes:
        print("·", n)
    if problems:
        print("Формальная проверка — есть замечания:")
        for x in problems:
            print("✗", x)
        print("Содержание оценивает ментор после исправления формы.")
        return 1
    print("✓ Форма в порядке. Содержание оценивает ментор.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("packet")
    p.add_argument("--questions", type=int, default=6)
    p.add_argument("--practice", action="store_true")
    p.add_argument("--stage", type=int, default=1)
    p.set_defaults(f=cmd_init)
    p = sub.add_parser("run")
    p.add_argument("packet")
    p.set_defaults(f=cmd_run)
    a = ap.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
