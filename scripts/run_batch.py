"""
Fase 4 — orquestração externa: vários produtos, uma execução de main.py por linha.

Arquivo de lista (UTF-8): uma linha por produto.
  termo de busca|custo_opcional|caminho_ml_json_opcional

Exemplos:
  fone bluetooth|35|
  mouse usb||D:/dados/ml_mouse.json

Saída CSV (append) com código de saída de cada execução.

Uso (na raiz do projeto):
  python scripts/run_batch.py scripts/products.txt --csv data/batch_resultados.csv
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


def _parse_line(line: str) -> tuple[str, str | None, str | None]:
    parts = [p.strip() for p in line.split("|")]
    while len(parts) < 3:
        parts.append("")
    query, cost_s, ml_json_s = parts[0], parts[1] or None, parts[2] or None
    return query, cost_s, ml_json_s


def main() -> None:
    p = argparse.ArgumentParser(description="Batch: chama main.py por produto.")
    p.add_argument("lista", type=Path, help="Arquivo de linhas query|custo|ml_json")
    p.add_argument("--csv", type=Path, required=True, help="CSV de saída (acrescenta linhas)")
    p.add_argument("--taxa-ml", type=float, default=0.16)
    p.add_argument("--historico", type=Path, default=None, help="Repassado ao main.py quando definido")
    args = p.parse_args()

    if not MAIN.is_file():
        print(f"main.py não encontrado em {MAIN}", file=sys.stderr)
        raise SystemExit(1)

    lines = [
        ln.strip()
        for ln in args.lista.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    new_file = not args.csv.is_file()
    with args.csv.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(
                [
                    "ts_utc",
                    "query",
                    "custo_arg",
                    "ml_json",
                    "exit_code",
                ]
            )
        for line in lines:
            query, cost_s, ml_json_s = _parse_line(line)
            if not query:
                continue
            cmd = [sys.executable, str(MAIN), query, "--taxa-ml", str(args.taxa_ml)]
            if cost_s:
                cmd += ["--custo", cost_s]
            if ml_json_s:
                cmd += ["--ml-json", ml_json_s]
            if args.historico is not None:
                cmd += ["--historico", str(args.historico)]

            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            ts = datetime.now(timezone.utc).isoformat()
            w.writerow([ts, query, cost_s or "", ml_json_s or "", r.returncode])
            f.flush()
            # Saída humana opcional
            print(f"[{r.returncode}] {query}")
            if r.stdout:
                print(r.stdout, end="")
            if r.stderr:
                print(r.stderr, end="", file=sys.stderr)


if __name__ == "__main__":
    main()
