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


commands = sorted_md(".claude/commands/*.md")

parts = [
    ("ЧАСТЬ 0. Правила Наставника", ["tools/project-instructions.md", "CLAUDE.md"] + commands),
    ("ЧАСТЬ 1. Мастерская: инструментарий и разборы (ядро курса)", ["dramaturgy/README.md"] + [p for p in sorted_md("dramaturgy/*.md") if not p.endswith("README.md")]),
    ("ЧАСТЬ 2. Программа, оценивание, справочники", ["curriculum/program.md", "curriculum/grading.md", "curriculum/craft.md"] + sorted_md("curriculum/myth/*.md") + sorted_md("curriculum/canon/*.md")),
    ("ЧАСТЬ 3. Шаблоны студентки (профиль, ведомость, портфолио)", sorted_md("student/*.md")),
    ("ЧАСТЬ 4. Лекции — справочник по контексту", ["lectures/README.md"] + [p for p in sorted_md("lectures/*.md") if not p.endswith("README.md")]),
]

header = """# Курс «Литературное мастерство и интертекст» — весь курс в одном файле

Этот файл — база знаний для проекта на claude.ai. Он состоит из пяти частей; каждый исходный файл курса — раздел с заголовком «[ФАЙЛ: путь]».
Когда в правилах упоминается путь (например, `dramaturgy/03-rossiya-xix.md` или команда `/razbor`), ищите соответствующий раздел в этом файле.

**Особенности работы в проекте claude.ai** (важнее правил ЧАСТИ 0, где они противоречат):
- Наставник не может создавать и менять файлы. Всё, что в правилах названо «запиши в student/…», он выдаёт в конце занятия одним блоком «ВЕДОМОСТЬ — ОБНОВЛЁННАЯ»; студентка сохраняет его в своём файле `moya-vedomost.md` в знаниях проекта.
- Команды со слешем (`/razbor`, `/start`…) работают как слова-режимы: «Разбор: …», «Диагностика» и т. д. Описание каждой команды — в разделах `[ФАЙЛ: .claude/commands/…]`.
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
