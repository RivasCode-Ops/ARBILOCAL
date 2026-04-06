"""
Busca na web orientada a fornecedores (resultados genéricos da internet).

A consulta roda **no servidor** (chaves nunca vão ao navegador). É necessário
configurar ao menos uma API de busca — respeite cotas e termos de uso.

Prioridade: 1) Brave  2) Serper (google.serper.dev)  3) Google Custom Search JSON (CSE).

Variáveis de ambiente:
  BRAVE_API_KEY          — https://api.search.brave.com/
  SERPER_API_KEY         — https://serper.dev/ — POST em google.serper.dev/search, header X-API-KEY
  SERPER_USE_GOOGLE_KEY  — se "1", usa GOOGLE_API_KEY como chave Serper (quando não há GOOGLE_CSE_ID)
  GOOGLE_API_KEY + GOOGLE_CSE_ID — API oficial Custom Search (não é Serper)
  ARBILOCAL_BUSCA_FORNECEDOR_SUFFIX — sufixo opcional na query quando enriquecer=1
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_SUFFIX = "fornecedor atacado distribuidor compra B2B Brasil"


def _serper_key() -> str | None:
    s = os.environ.get("SERPER_API_KEY", "").strip()
    if s:
        return s
    use_gk = os.environ.get("SERPER_USE_GOOGLE_KEY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "sim",
        "on",
    )
    cx = (os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX") or "").strip()
    if use_gk and not cx:
        gk = os.environ.get("GOOGLE_API_KEY", "").strip()
        if gk:
            return gk
    return None


def busca_web_configurada() -> bool:
    if os.environ.get("BRAVE_API_KEY", "").strip():
        return True
    if _serper_key():
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


def _serper_search(q: str, limit: int, key: str) -> list[dict[str, str]]:
    """Serper: POST https://google.serper.dev/search — header X-API-KEY."""
    url = "https://google.serper.dev/search"
    n = min(max(1, limit), 20)
    with httpx.Client(timeout=25.0) as client:
        r = client.post(
            url,
            headers={
                "X-API-KEY": key,
                "Content-Type": "application/json",
            },
            json={"q": q, "num": n},
        )
        r.raise_for_status()
        data = r.json()
    organic = data.get("organic") if isinstance(data, dict) else None
    if not isinstance(organic, list):
        organic = []
    out: list[dict[str, str]] = []
    for it in organic[:n]:
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

    sk = _serper_key()
    err_serper: str | None = None
    if sk:
        try:
            res = _serper_search(q, lim, sk)
            return {"ok": True, "fonte": "serper", "query": q, "resultados": res}
        except Exception as e:
            err_serper = str(e)

    gk = os.environ.get("GOOGLE_API_KEY", "").strip()
    cx = (os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX") or "").strip()
    if gk and cx:
        try:
            res = _google_cse(q, lim, gk, cx)
            return {"ok": True, "fonte": "google_cse", "query": q, "resultados": res}
        except Exception as e:
            msg = f"Google CSE: {e}"
            parts = [p for p in (err_brave, err_serper) if p]
            if parts:
                msg = "; ".join(parts) + "; " + msg
            return {"ok": False, "erro": msg}

    parts_err = [p for p in (err_brave, err_serper) if p]
    if parts_err:
        return {
            "ok": False,
            "erro": "Falha na busca: " + "; ".join(parts_err),
        }
    return {
        "ok": False,
        "erro": (
            "Busca web não configurada. Defina BRAVE_API_KEY, ou SERPER_API_KEY "
            "(Serper), ou GOOGLE_API_KEY+GOOGLE_CSE_ID (API oficial). "
            "Para usar chave Serper em GOOGLE_API_KEY sem CSE: SERPER_USE_GOOGLE_KEY=1."
        ),
    }
