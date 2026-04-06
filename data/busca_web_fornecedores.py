"""
Busca na web orientada a fornecedores (resultados genéricos da internet).

A consulta roda **no servidor** (chaves nunca vão ao navegador). É necessário
configurar ao menos uma API de busca — respeite cotas e termos de uso.

Prioridade: 1) Brave Search API  2) Google Programmable Search (Custom Search JSON).

Variáveis de ambiente:
  BRAVE_API_KEY          — https://api.search.brave.com/
  GOOGLE_API_KEY         — Custom Search JSON API
  GOOGLE_CSE_ID ou GOOGLE_CX — ID do mecanismo de busca programável (cx)
  ARBILOCAL_BUSCA_FORNECEDOR_SUFFIX — sufixo opcional na query quando enriquecer=1
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_SUFFIX = "fornecedor atacado distribuidor compra B2B Brasil"


def busca_web_configurada() -> bool:
    if os.environ.get("BRAVE_API_KEY", "").strip():
        return True
    gk = os.environ.get("GOOGLE_API_KEY", "").strip()
    cx = (os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX") or "").strip()
    return bool(gk and cx)


def _montar_query(termo: str, enriquecer: bool) -> str:
    t = (termo or "").strip()
    if not t:
        raise ValueError("termo vazio")
    if not enriquecer:
        return t
    suf = os.environ.get("ARBILOCAL_BUSCA_FORNECEDOR_SUFFIX", DEFAULT_SUFFIX).strip()
    return f"{t} {suf}" if suf else t


def _brave_search(q: str, limit: int, key: str) -> list[dict[str, str]]:
    url = "https://api.search.brave.com/res/v1/web/search"
    n = min(max(1, limit), 20)
    with httpx.Client(timeout=25.0) as client:
        r = client.get(
            url,
            params={"q": q, "count": str(n)},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": key,
            },
        )
        r.raise_for_status()
        data = r.json()
    web = data.get("web") if isinstance(data, dict) else None
    raw = (web or {}).get("results") if isinstance(web, dict) else None
    if not isinstance(raw, list):
        raw = []
    out: list[dict[str, str]] = []
    for it in raw[:n]:
        if not isinstance(it, dict):
            continue
        desc = it.get("description")
        if not desc and isinstance(it.get("extra_snippets"), list) and it["extra_snippets"]:
            desc = it["extra_snippets"][0]
        out.append(
            {
                "titulo": str(it.get("title") or "")[:500],
                "url": str(it.get("url") or "")[:2000],
                "trecho": str(desc or "")[:900],
            }
        )
    return out


def _google_cse(q: str, limit: int, key: str, cx: str) -> list[dict[str, str]]:
    url = "https://www.googleapis.com/customsearch/v1"
    n = min(max(1, limit), 10)
    with httpx.Client(timeout=25.0) as client:
        r = client.get(
            url,
            params={"key": key, "cx": cx, "q": q, "num": str(n)},
        )
        r.raise_for_status()
        data = r.json()
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        items = []
    out: list[dict[str, str]] = []
    for it in items[:n]:
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "titulo": str(it.get("title") or "")[:500],
                "url": str(it.get("link") or "")[:2000],
                "trecho": str(it.get("snippet") or "")[:900],
            }
        )
    return out


def executar_busca_fornecedores(
    termo: str,
    *,
    limit: int = 10,
    enriquecer: bool = True,
) -> dict[str, Any]:
    """
    Retorna dict com ok, query, fonte, resultados (lista de titulo/url/trecho)
    ou ok=False e erro.
    """
    try:
        q = _montar_query(termo, enriquecer)
    except ValueError as e:
        return {"ok": False, "erro": str(e)}

    lim = min(max(1, int(limit)), 20)

    brave = os.environ.get("BRAVE_API_KEY", "").strip()
    err_brave: str | None = None
    if brave:
        try:
            res = _brave_search(q, lim, brave)
            return {"ok": True, "fonte": "brave", "query": q, "resultados": res}
        except Exception as e:
            err_brave = str(e)

    gk = os.environ.get("GOOGLE_API_KEY", "").strip()
    cx = (os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX") or "").strip()
    if gk and cx:
        try:
            res = _google_cse(q, lim, gk, cx)
            return {"ok": True, "fonte": "google_cse", "query": q, "resultados": res}
        except Exception as e:
            msg = f"Google CSE: {e}"
            if err_brave:
                msg = f"Brave: {err_brave}; {msg}"
            return {"ok": False, "erro": msg}

    if err_brave:
        return {
            "ok": False,
            "erro": f"Brave Search falhou: {err_brave}. Configure GOOGLE_API_KEY+GOOGLE_CSE_ID como fallback.",
        }
    return {
        "ok": False,
        "erro": (
            "Busca web não configurada no servidor. Defina BRAVE_API_KEY "
            "(recomendado) ou GOOGLE_API_KEY + GOOGLE_CSE_ID (Custom Search JSON)."
        ),
    }
