"""
Fase 3 — script externo: grava a resposta bruta da busca do ML (mesmo formato de --ml-json).

Uso (na raiz do projeto):
  python scripts/save_ml_search.py "fone bluetooth" data/ml_ultima_busca.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.mercado_livre import MercadoLivreClient  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Salva JSON da busca MLB (API oficial).")
    p.add_argument("query", help="Termo de busca")
    p.add_argument("out", type=Path, help="Arquivo .json de saída")
    args = p.parse_args()

    client = MercadoLivreClient()
    try:
        raw = client.search_raw(args.query, limit=50)
    except Exception as e:
        print(f"Falha ao buscar no Mercado Livre: {e}", file=sys.stderr)
        raise SystemExit(1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f"Gravado: {args.out.resolve()}")


if __name__ == "__main__":
    main()
