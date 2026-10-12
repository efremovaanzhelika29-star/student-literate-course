#!/usr/bin/env python3
"""Собирает весь курс в один файл для загрузки в проект claude.ai.

Запуск из корня репозитория:  python3 tools/build_bundle.py
Результат: kurs-literaturnoe-masterstvo.md
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "kurs-literaturnoe-masterstvo.md")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read().strip()


def sorted_md(pattern):
    return sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, pattern)))


def demote(text):
    # Сдвигаем заголовки на два уровня, чтобы части файла оставались верхним уровнем.
    return re.sub(r"^(#{1,4}) ", lambda m: "#" * min(len(m.group(1)) + 2, 6) + " ", text, flags=re.M)


def section(rel):
    return f"\n\n---\n\n## [ФАЙЛ: {rel}]\n\n{demote(read(rel))}\n"


skills = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, ".claude/skills/*/SKILL.md")))
stage_docs = sorted_md("0[0-9]-*.md") + sorted_md("10-*.md")

parts = [
    ("ЧАСТЬ 0. Правила ментора", ["tools/project-instructions.md", "CLAUDE.md", "mentoring/harness.md", "mentoring/format.md", "mentoring/lesson-packets.md", "mentoring/rubrics.md"] + skills),
    ("ЧАСТЬ 1. Этапы, чекпоинты, Сборник, карьера", ["README.md"] + stage_docs + ["resources.md"]),
    ("ЧАСТЬ 2. Мастерская: инструментарий и разборы (ядро курса)", ["knowledge/dramaturgy/README.md"] + [p for p in sorted_md("knowledge/dramaturgy/*.md") if not p.endswith("README.md")]),
    ("ЧАСТЬ 3. Справочники", ["knowledge/reference/craft.md"] + sorted_md("knowledge/reference/myth/*.md") + sorted_md("knowledge/reference/canon/*.md")),
    ("ЧАСТЬ 4. Шаблоны ученицы", sorted_md("templates/state/*.md")),
    ("ЧАСТЬ 5. Лекции — справочник по контексту", ["knowledge/lectures/README.md"] + [p for p in sorted_md("knowledge/lectures/*.md") if not p.endswith("README.md")]),
]

header = """# Курс «Литературное мастерство и интертекст» — весь курс в одном файле

Этот файл — база знаний для проекта на claude.ai. Он состоит из пяти частей; каждый исходный файл курса — раздел с заголовком «[ФАЙЛ: путь]».
Когда в правилах упоминается путь (например, `knowledge/dramaturgy/03-rossiya-xix.md` или команда `/razbor`), ищите соответствующий раздел в этом файле.

**Особенности работы в проекте claude.ai** (важнее правил ЧАСТИ 0, где они противоречат):
- Наставник не может создавать и менять файлы. Всё, что в правилах названо «запиши в student/…», он выдаёт в конце занятия одним блоком «ВЕДОМОСТЬ — ОБНОВЛЁННАЯ»; студентка сохраняет его в своём файле `moya-vedomost.md` в знаниях проекта.
- Скрипты (`bin/*.py`) и трекер здесь недоступны. Команды `/status`, `/learn`, `/check`, `/review`, `/mock` работают как слова-режимы; их описание — в разделах `[ФАЙЛ: .claude/skills/…]`. Протоколы и статусы ментор выдаёт текстом в блоке «ВЕДОМОСТЬ».
- Агента `quote-checker` здесь нет: если факт не проверен, Наставник прямо так и говорит.

## Оглавление
"""

body = []
toc = []
for title, files in parts:
    toc.append(f"- **{title}**: " + ", ".join(f"`{f}`" for f in files))
    body.append(f"\n\n# {title}\n" + "".join(section(f) for f in files))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(header + "\n".join(toc) + "\n" + "".join(body))

size = os.path.getsize(OUT)
print(f"{os.path.relpath(OUT, ROOT)}: {size/1024/1024:.2f} МБ")
