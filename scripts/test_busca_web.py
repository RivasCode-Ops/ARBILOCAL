#!/usr/bin/env python3
"""Testa a busca web no terminal (lê .env). Uso: python scripts/test_busca_web.py [termo]

Útil quando “no navegador não funciona”: aqui vês o erro real do Python/SearXNG.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from data.busca_web_fornecedores import diagnostico_busca, executar_busca_fornecedores  # noqa: E402


def main() -> int:
    termo = sys.argv[1] if len(sys.argv) > 1 else "teste"
    print("=== Diagnóstico (sem chaves) ===")
    print(json.dumps(diagnostico_busca(), indent=2, ensure_ascii=False))
    print("\n=== Busca de teste (enriquecer=False, limite=3) ===")
    r = executar_busca_fornecedores(termo, limit=3, enriquecer=False)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    if not r.get("ok"):
        print("\nSe falhou SearXNG: abra no browser o campo searxng_teste_no_browser do JSON acima.", file=sys.stderr)
        return 1
    print("\nOK — se o painel falhar, é cache do browser ou URL errada na barra de endereço (use http://127.0.0.1:8765/).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
