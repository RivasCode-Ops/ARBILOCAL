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

from data.busca_web_fornecedores import _serper_key, busca_web_configurada  # noqa: E402


def main() -> int:
    import os

    br = bool(os.environ.get("BRAVE_API_KEY", "").strip())
    gk = bool(os.environ.get("GOOGLE_API_KEY", "").strip())
    cx = bool((os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX") or "").strip())
    sr = bool(os.environ.get("SERPER_API_KEY", "").strip())
    sgk = bool(os.environ.get("SERPER_USE_GOOGLE_KEY", "").strip().lower() in ("1", "true", "yes", "sim", "on"))
    serper_ok = bool(_serper_key())

    print("=== Pesquisa web (fornecedores) ===\n")
    if busca_web_configurada():
        print("Status: OK — pelo menos uma fonte está configurada.\n")
    else:
        print("Status: NÃO configurado.\n")
        print("Veja .env.example: Brave, Serper ou Google CSE oficial.\n")

    print(f"  BRAVE_API_KEY:        {'sim' if br else 'não'}")
    print(f"  SERPER_API_KEY:       {'sim' if sr else 'não'}")
    print(f"  Serper via GOOGLE_KEY: {'sim' if sgk and not cx else 'não'} (SERPER_USE_GOOGLE_KEY + GOOGLE_API_KEY sem CSE)")
    print(f"  Chave Serper resolvida: {'sim' if serper_ok else 'não'}")
    print(f"  GOOGLE_API_KEY:       {'sim' if gk else 'não'} (CSE oficial se houver cx)")
    print(f"  GOOGLE_CSE_ID:        {'sim' if cx else 'não'}")
    print(f"\nArquivo .env em: {ROOT / '.env'}")
    return 0 if busca_web_configurada() else 1


if __name__ == "__main__":
    raise SystemExit(main())
