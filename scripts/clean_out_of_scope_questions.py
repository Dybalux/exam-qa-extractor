#!/usr/bin/env python3
"""Clean out-of-scope questions from database.db, sync docker DB, and export JSON."""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
import sys
from pathlib import Path

OUT_OF_SCOPE_IDS = [102, 103, 104, 105, 108, 109, 113, 114, 115]

DB_PATH = Path("/home/dybalux/Escritorio_Dev/image_to_text/database.db")
DOCKER_DB_PATH = Path("/home/dybalux/Escritorio_Dev/image_to_text/data/db/database.db")
JSON_PATH = Path(
    "/home/dybalux/Escritorio_Facutad/Sistemas Operativos/Sistemas Operativos.json"
)


async def main() -> None:
    print("=" * 65)
    print("AUDIT & CLEAN OUT-OF-SCOPE QUESTIONS FOR TERCER PARCIAL")
    print("=" * 65)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Pre-clean check
    initial_q = cur.execute("SELECT count(*) FROM questions").fetchone()[0]
    initial_a = cur.execute("SELECT count(*) FROM answers").fetchone()[0]
    print("Initial DB state:")
    print(f"  Questions: {initial_q}")
    print(f"  Answers:   {initial_a}")

    # Inspect targets
    placeholders = ",".join("?" for _ in OUT_OF_SCOPE_IDS)
    cur.execute(
        f"""
        SELECT q.id, t.name, q.question_text
        FROM questions q
        JOIN topics t ON q.topic_id = t.id
        WHERE q.id IN ({placeholders})
        ORDER BY q.id
        """,
        OUT_OF_SCOPE_IDS,
    )
    targets = cur.fetchall()
    print(f"\nIdentified {len(targets)} out-of-scope questions to delete:")
    for qid, tname, text in targets:
        print(f"  - [ID {qid}] [{tname}] {text}")

    if len(targets) != len(OUT_OF_SCOPE_IDS):
        print(
            f"WARNING: Expected {len(OUT_OF_SCOPE_IDS)} questions, found {len(targets)}"
        )

    # Delete answers first (though CASCADE is defined, explicit delete is safe)
    cur.execute(
        f"DELETE FROM answers WHERE question_id IN ({placeholders})",
        OUT_OF_SCOPE_IDS,
    )
    deleted_answers = cur.rowcount
    print(f"\nDeleted {deleted_answers} answer rows.")

    # Delete questions
    cur.execute(
        f"DELETE FROM questions WHERE id IN ({placeholders})",
        OUT_OF_SCOPE_IDS,
    )
    deleted_questions = cur.rowcount
    print(f"Deleted {deleted_questions} question rows.")

    # Foreign key check
    cur.execute("PRAGMA foreign_key_check;")
    fk_errors = cur.fetchall()
    if fk_errors:
        print(f"FATAL: PRAGMA foreign_key_check failed: {fk_errors}")
        conn.rollback()
        sys.exit(1)
    else:
        print("PRAGMA foreign_key_check: OK (0 errors)")

    # Integrity check
    cur.execute("PRAGMA integrity_check;")
    integrity = cur.fetchall()
    print(f"PRAGMA integrity_check: {integrity[0][0]}")
    if integrity[0][0] != "ok":
        print(f"FATAL: Database integrity corrupted: {integrity}")
        conn.rollback()
        sys.exit(1)

    # Commit
    conn.commit()

    final_q = cur.execute("SELECT count(*) FROM questions").fetchone()[0]
    final_a = cur.execute("SELECT count(*) FROM answers").fetchone()[0]
    print("\nPost-clean DB counts:")
    print(f"  Questions: {final_q} (was {initial_q}, -{initial_q - final_q})")
    print(f"  Answers:   {final_a} (was {initial_a}, -{initial_a - final_a})")

    # Topic distribution
    print("\nTopic Breakdown post-clean:")
    topic_dist = cur.execute(
        """
        SELECT t.id, t.name, count(q.id)
        FROM topics t
        LEFT JOIN questions q ON q.topic_id = t.id
        GROUP BY t.id, t.name
        ORDER BY t.id
        """
    ).fetchall()
    for tid, tname, count in topic_dist:
        print(f"  Topic {tid} ({tname}): {count} questions")

    conn.close()

    # Sync to docker db
    shutil.copy2(DB_PATH, DOCKER_DB_PATH)
    print(f"\nSynced clean database to {DOCKER_DB_PATH}")

    # Export to JSON via JsonIOService
    print("\nExporting full database to JSON via JsonIOService...")
    from app.db.session import AsyncSessionLocal
    from app.schemas.json_io import ExportFileSchema
    from app.services.json_io_service import JsonIOService

    async with AsyncSessionLocal() as session:
        service = JsonIOService(session)
        export_data = await service.export_full_db()
        dumped = export_data.model_dump(mode="json")

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(dumped, f, indent=2)
            f.write("\n")

        print(f"Wrote {len(dumped['questions'])} questions to {JSON_PATH}")

        # Validate with pydantic
        validated = ExportFileSchema.model_validate(dumped)
        print(
            f"Export validation successful: {len(validated.questions)} questions validated."
        )


if __name__ == "__main__":
    asyncio.run(main())
