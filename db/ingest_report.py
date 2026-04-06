"""
Ingere reports/*.json no SQLite — fora do núcleo (não chama run()).

Uso (raiz do projeto):
  python db/ingest_report.py
  python db/ingest_report.py --reports-dir reports --db db/database.db
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS_DIR = ROOT / "reports"
DEFAULT_DB_PATH = ROOT / "db" / "database.db"
DEFAULT_SCHEMA_PATH = ROOT / "db" / "schema.sql"

REQUIRED_REPORT_KEYS = frozenset(
    {"produto", "preco_medio", "custo", "lucro", "margem", "concorrencia", "recomendacao"}
)

TS_FROM_NAME = re.compile(r"report_(\d{8}T\d{6}Z)_", re.IGNORECASE)


def _setup_log(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )


def ensure_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    if not schema_path.is_file():
        raise FileNotFoundError(f"schema não encontrado: {schema_path}")
    sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def migrate_analysis_run_time_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_run'")
    if cur.fetchone() is None:
        return
    cur = conn.execute("PRAGMA table_info(analysis_run)")
    cols = {row[1] for row in cur.fetchall()}
    if "generated_at" not in cols:
        conn.execute("ALTER TABLE analysis_run ADD COLUMN generated_at TEXT")
    if "ingested_at" not in cols:
        conn.execute("ALTER TABLE analysis_run ADD COLUMN ingested_at TEXT")
    conn.commit()


def _parse_report_timestamp(path: Path) -> str | None:
    m = TS_FROM_NAME.search(path.name)
    if not m:
        return None
    raw = m.group(1)
    # 20260405T203422Z -> ISO-ish
    try:
        d = raw[:8]
        t = raw[9:15]
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}Z"
    except Exception:
        return raw


def load_report_json(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logging.warning("ignorado (leitura): %s — %s", path, e)
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logging.warning("ignorado (JSON inválido): %s — %s", path, e)
        return None
    if not isinstance(data, dict):
        logging.warning("ignorado (raiz não é objeto): %s", path)
        return None
    missing = REQUIRED_REPORT_KEYS - data.keys()
    if missing:
        logging.warning("ignorado (campos ausentes %s): %s", sorted(missing), path)
        return None
    return data


def _extract_generated_at(data: dict, path: Path) -> str | None:
    ga = data.get("generated_at")
    if isinstance(ga, str) and ga.strip():
        return ga.strip()
    legacy = data.get("timestamp")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()
    return _parse_report_timestamp(path)


def insert_analysis_run(conn: sqlite3.Connection, path: Path, data: dict) -> bool:
    report_path = str(path.resolve())
    generated_at = _extract_generated_at(data, path)
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = (
        data["produto"],
        float(data["custo"]),
        None,
        None,
        None,
        report_path,
        0,
        float(data["preco_medio"]),
        float(data["lucro"]),
        float(data["margem"]),
        str(data["concorrencia"]),
        str(data["recomendacao"]),
        data.get("motivo"),
        data.get("veredito"),
        data.get("risco"),
        data.get("resultado_final"),
        generated_at,
        ingested_at,
        "report_json",
    )
    try:
        conn.execute(
            """
            INSERT INTO analysis_run (
                query_text, cost_brl, ml_fee_rate, ml_total_results, ml_sample_size,
                report_path, exit_code,
                preco_medio, lucro, margem, concorrencia, recomendacao,
                motivo, veredito, risco, resultado_final,
                generated_at, ingested_at, ingest_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            logging.info("já ingerido (report_path): %s", path.name)
            return False
        logging.warning("ignorado (integridade): %s — %s", path, e)
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="Ingere reports/*.json no SQLite.")
    p.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="Pasta com report_*.json")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Caminho do database.db")
    p.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="schema.sql para criar tabelas")
    p.add_argument("--init-only", action="store_true", help="Só aplica schema e sai")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    _setup_log(args.verbose)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(args.db))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_schema(conn, args.schema)
        migrate_analysis_run_time_columns(conn)
        if args.init_only:
            logging.info("schema aplicado em %s", args.db)
            return 0

        if not args.reports_dir.is_dir():
            logging.warning("pasta de reports inexistente: %s", args.reports_dir)
            return 0

        files = sorted(args.reports_dir.glob("*.json"))
        inserted = 0
        for path in files:
            data = load_report_json(path)
            if data is None:
                continue
            if insert_analysis_run(conn, path, data):
                inserted += 1
                logging.info("ingerido: %s", path.name)
        conn.commit()
        logging.info("concluído: %s arquivo(s) novos", inserted)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
