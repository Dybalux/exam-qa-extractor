#!/usr/bin/env python3
"""Clean question answer options where explanations were erroneously concatenated.

In affected rows, answer options had explanations appended after ': ' while
the explanation column was left NULL.
This script:
1. Splits affected answer options into clean option text and explanation text.
2. Removes spurious 'Opción A: ' prefixes.
3. Preserves legitimate colons (e.g. 'time' command output definitions).
4. Updates database.db, data/db/database.db, and database_backup_20260630_232738.json.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def process_answer(
    answer_text: str,
    explanation: str | None,
) -> tuple[str, str | None, str]:
    """Process an answer text and explanation.

    Returns:
        (new_answer_text, new_explanation, action_taken)
        action_taken is one of 'split', 'prefix_cleaned', 'skipped'
    """
    if ": " not in answer_text:
        return answer_text, explanation, "skipped"

    # Already has a non-empty explanation
    if explanation is not None and len(explanation.strip()) > 0:
        return answer_text, explanation, "skipped"

    # Legitimate multi-value definition (Q41: 'time' values System/User/Real)
    if answer_text.startswith("System:"):
        return answer_text, explanation, "skipped"

    # Prefix artifact: 'Opción A: ...'
    if answer_text.startswith("Opción A: "):
        cleaned_text = answer_text[len("Opción A: ") :].strip()
        return cleaned_text, explanation, "prefix_cleaned"

    # Explanation concatenated with ': '
    parts = answer_text.split(": ", 1)
    clean_opt = parts[0].strip()

    # Clean leading dots or whitespace artifacts
    if clean_opt.startswith(". "):
        clean_opt = clean_opt[2:].strip()

    # Fix OCR missing initial letter in 'nterfaz'
    if clean_opt.startswith("nterfaz "):
        clean_opt = "I" + clean_opt

    clean_expl = parts[1].strip()
    return clean_opt, clean_expl, "split"


def clean_sqlite_db(db_path: Path, dry_run: bool = False) -> dict[str, int]:
    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return {"total": 0, "split": 0, "prefix_cleaned": 0, "skipped": 0}

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing SQLite DB: {db_path}")

    # Backup before modification
    if not dry_run:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.with_name(f"{db_path.name}.bak_{timestamp}")
        shutil.copy2(db_path, backup_path)
        print(f"  Created backup at: {backup_path}")

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    rows = cur.execute(
        "SELECT id, question_id, answer_type, answer_text, explanation FROM answers ORDER BY id"
    ).fetchall()

    counts = {"total": len(rows), "split": 0, "prefix_cleaned": 0, "skipped": 0}
    examples: list[dict] = []

    for aid, qid, atype, atext, aexpl in rows:
        new_text, new_expl, action = process_answer(atext, aexpl)
        counts[action] += 1

        if action in ("split", "prefix_cleaned"):
            if not dry_run:
                cur.execute(
                    "UPDATE answers SET answer_text = ?, explanation = ? WHERE id = ?",
                    (new_text, new_expl, aid),
                )
            if len(examples) < 5 or action == "prefix_cleaned":
                examples.append(
                    {
                        "id": aid,
                        "question_id": qid,
                        "action": action,
                        "before_text": atext,
                        "after_text": new_text,
                        "after_expl": new_expl,
                    }
                )

    if not dry_run:
        con.commit()
    con.close()

    print(f"  Total answers: {counts['total']}")
    print(f"  Split into option + explanation: {counts['split']}")
    print(f"  Cleaned 'Opción A:' prefix: {counts['prefix_cleaned']}")
    print(f"  Skipped (unchanged / legitimate): {counts['skipped']}")

    if examples:
        print("\n  Sample Updates:")
        for ex in examples:
            print(
                f"    - ID {ex['id']} (Q{ex['question_id']}, action: {ex['action']}):"
            )
            print(f"        BEFORE TEXT: {ex['before_text'][:80]}...")
            print(f"        AFTER TEXT:  {ex['after_text']}")
            print(f"        AFTER EXPL:  {str(ex['after_expl'])[:80]}...")

    return counts


def clean_json_backup(json_path: Path, dry_run: bool = False) -> dict[str, int]:
    if not json_path.exists():
        print(f"JSON file not found: {json_path}")
        return {"total": 0, "split": 0, "prefix_cleaned": 0, "skipped": 0}

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing JSON backup: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "answers" not in data or not isinstance(data["answers"], list):
        print(f"  No 'answers' list found in {json_path}")
        return {"total": 0, "split": 0, "prefix_cleaned": 0, "skipped": 0}

    # Backup before modification
    if not dry_run:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = json_path.with_name(f"{json_path.name}.bak_{timestamp}")
        shutil.copy2(json_path, backup_path)
        print(f"  Created backup at: {backup_path}")

    counts = {
        "total": len(data["answers"]),
        "split": 0,
        "prefix_cleaned": 0,
        "skipped": 0,
    }

    for item in data["answers"]:
        atext = item.get("answer_text", "")
        aexpl = item.get("explanation")
        new_text, new_expl, action = process_answer(atext, aexpl)
        counts[action] += 1

        if action in ("split", "prefix_cleaned"):
            item["answer_text"] = new_text
            item["explanation"] = new_expl

    if not dry_run:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    print(f"  Total answers: {counts['total']}")
    print(f"  Split into option + explanation: {counts['split']}")
    print(f"  Cleaned 'Opción A:' prefix: {counts['prefix_cleaned']}")
    print(f"  Skipped (unchanged / legitimate): {counts['skipped']}")

    return counts


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    repo_root = Path(__file__).resolve().parent.parent

    db_path = repo_root / "database.db"
    docker_db_path = repo_root / "data" / "db" / "database.db"
    json_path = repo_root / "database_backup_20260630_232738.json"

    print("=== Clean Answer Explanations Tool ===")
    clean_sqlite_db(db_path, dry_run=dry_run)
    clean_sqlite_db(docker_db_path, dry_run=dry_run)
    clean_json_backup(json_path, dry_run=dry_run)
    print("\nCompleted successfully!")


if __name__ == "__main__":
    main()
