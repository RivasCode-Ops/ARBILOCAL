"""
Histórico simples de análises (Fase 5): uma linha JSON por execução (JSONL).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_analysis_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
