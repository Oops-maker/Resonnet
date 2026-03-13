"""Sync discussion turn markdown files into database rows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import uuid

from sqlalchemy import select

from app.agent.workspace import _get_expert_label
from app.db.models import DiscussionTurnRecord
from app.db.session import session_scope


_TURN_FILE_RE = re.compile(r"round(\d+)_(.+)")


def _file_datetime(path: Path) -> datetime:
    value = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _turn_id(topic_id: str, turn_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"discussion-turn:{topic_id}:{turn_key}"))


def sync_discussion_turns(ws_path: Path) -> int:
    """Mirror shared/turns/*.md into discussion_turns for the topic."""
    topic_id = ws_path.name
    turns_dir = ws_path / "shared" / "turns"
    if not turns_dir.exists():
        return 0

    turn_files = sorted(turns_dir.glob("*.md"))
    turn_ids = set()

    with session_scope() as session:
        existing_rows = session.scalars(
            select(DiscussionTurnRecord).where(DiscussionTurnRecord.topic_id == topic_id)
        ).all()
        existing_by_id = {row.id: row for row in existing_rows}

        for turn_file in turn_files:
            turn_key = turn_file.stem
            turn_id = _turn_id(topic_id, turn_key)
            turn_ids.add(turn_id)

            match = _TURN_FILE_RE.fullmatch(turn_key)
            round_num = int(match.group(1)) if match else None
            expert_name = match.group(2) if match else None
            expert_label = _get_expert_label(expert_name, ws_path) if expert_name else turn_key
            body = turn_file.read_text(encoding="utf-8").strip()
            updated_at = _file_datetime(turn_file)

            row = existing_by_id.get(turn_id)
            if row is None:
                row = DiscussionTurnRecord(
                    id=turn_id,
                    topic_id=topic_id,
                    turn_key=turn_key,
                    round_num=round_num,
                    expert_name=expert_name,
                    expert_label=expert_label,
                    body=body,
                    source_file=turn_file.name,
                    created_at=updated_at,
                    updated_at=updated_at,
                )
                session.add(row)
                existing_by_id[turn_id] = row
                continue

            row.turn_key = turn_key
            row.round_num = round_num
            row.expert_name = expert_name
            row.expert_label = expert_label
            row.body = body
            row.source_file = turn_file.name
            row.updated_at = updated_at

        for row in existing_rows:
            if row.id not in turn_ids:
                session.delete(row)

    return len(turn_ids)
