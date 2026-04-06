#!/usr/bin/env python3
"""Mostra se a pesquisa web está configurada (lê .env se python-dotenv estiver instalado)."""

from __future__ import annotations

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

from data.busca_web_fornecedores import busca_web_configurada  # noqa: E402


def main() -> int:
    import os

    br = bool(os.environ.get("BRAVE_API_KEY", "").strip())
    gk = bool(os.environ.get("GOOGLE_API_KEY", "").strip())
    cx = bool((os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX") or "").strip())

    print("=== Pesquisa web (fornecedores) ===\n")
    if busca_web_configurada():
        print("Status: OK — pelo menos uma fonte está configurada.\n")
    else:
        print("Status: NÃO configurado.\n")
        print("Copie .env.example para .env e preencha BRAVE_API_KEY ou GOOGLE_API_KEY+GOOGLE_CSE_ID.\n")

    print(f"  BRAVE_API_KEY:     {'sim' if br else 'não'}")
    print(f"  GOOGLE_API_KEY:    {'sim' if gk else 'não'}")
    print(f"  GOOGLE_CSE_ID:     {'sim' if cx else 'não'}")
    print(f"\nArquivo .env em: {ROOT / '.env'}")
    return 0 if busca_web_configurada() else 1


if __name__ == "__main__":
    raise SystemExit(main())
