"""
Busca na web orientada a fornecedores (resultados genéricos da internet).

A consulta roda **no servidor** (chaves nunca vão ao navegador). É necessário
configurar ao menos uma API de busca — respeite cotas e termos de uso.

Prioridade: 1) SearXNG (instância própria)  2) Brave  3) Serper  4) Google CSE.

Variáveis de ambiente:
  SEARXNG_URL            — URL base da instância (ex.: https://search.exemplo.com ou http://127.0.0.1:8080)
  SEARXNG_API_KEY        — opcional; por defeito Authorization: Bearer …
  SEARXNG_API_KEY_HEADER — opcional; ex.: X-API-Key (valor = chave, sem Bearer)
  SEARXNG_USERNAME       — opcional; com SEARXNG_PASSWORD para HTTP Basic (proxy/nginx)
  SEARXNG_PASSWORD       — opcional
  SEARXNG_SSL_VERIFY     — 0 para desativar verificação SSL (só se necessário)
  SEARXNG_CATEGORIES     — opcional; ex.: general (vírgula = várias)
  BRAVE_API_KEY          — https://api.search.brave.com/
  SERPER_API_KEY         — https://serper.dev/ — POST em google.serper.dev/search, header X-API-KEY
  SERPER_USE_GOOGLE_KEY  — se "1", usa GOOGLE_API_KEY como chave Serper (quando não há GOOGLE_CSE_ID)
  GOOGLE_API_KEY + GOOGLE_CSE_ID — API oficial Custom Search (não é Serper)
  ARBILOCAL_BUSCA_FORNECEDOR_SUFFIX — sufixo opcional na query quando enriquecer=1

No SearXNG, ative JSON em settings.yml (search.formats incluir json), senão a API devolve 403.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urljoin

import httpx

DEFAULT_SUFFIX = "fornecedor atacado distribuidor compra B2B Brasil"


def _searxng_base_url() -> str | None:
    """URL base sem barra final; remove /search se o utilizador colou o endpoint completo."""
    u = (os.environ.get("SEARXNG_URL") or "").strip()
    if not u:
        return None
    u = u.rstrip("/")
    if u.lower().endswith("/search"):
        u = u[: -len("/search")].rstrip("/")
    return u


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
    if _searxng_base_url():
        return True
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


def _searxng_verify_ssl() -> bool:
    v = (os.environ.get("SEARXNG_SSL_VERIFY") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _searxng_headers_auth() -> tuple[dict[str, str], tuple[str, str] | None]:
    """Headers e tupla (user, pass) para Basic, se definidos."""
    headers: dict[str, str] = {"Accept": "application/json"}
    api_key = (os.environ.get("SEARXNG_API_KEY") or "").strip()
    if api_key:
        hdr_name = (os.environ.get("SEARXNG_API_KEY_HEADER") or "Authorization").strip()
        if hdr_name.lower() == "authorization":
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers[hdr_name] = api_key
    user = (os.environ.get("SEARXNG_USERNAME") or "").strip()
    pw = (os.environ.get("SEARXNG_PASSWORD") or "").strip()
    auth: tuple[str, str] | None = (user, pw) if (user or pw) else None
    return headers, auth


def _searxng_search(q: str, limit: int) -> list[dict[str, str]]:
    """
    GET {base}/search?q=...&format=json — ver documentação SearXNG Search API.
    Resultados: lista com title, url, content (snippet).
    """
    base = _searxng_base_url()
    if not base:
        raise RuntimeError("SearXNG: SEARXNG_URL não definido")
    n = min(max(1, limit), 20)
    search_url = urljoin(base + "/", "search")
    params: dict[str, str] = {"q": q, "format": "json"}
    cats = (os.environ.get("SEARXNG_CATEGORIES") or "").strip()
    if cats:
        params["categories"] = cats
    headers, auth = _searxng_headers_auth()
    verify = _searxng_verify_ssl()
    try:
        with httpx.Client(timeout=35.0, verify=verify, follow_redirects=True) as client:
            try:
                r = client.get(search_url, params=params, headers=headers, auth=auth)
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                body = ""
                try:
                    body = (e.response.text or "")[:500]
                except Exception:
                    pass
                hint = ""
                if e.response.status_code == 403:
                    hint = (
                        " (403: ative 'json' em search.formats no settings.yml do SearXNG; "
                        "instâncias públicas muitas vezes bloqueiam JSON — use a sua.)"
                    )
                raise RuntimeError(f"SearXNG HTTP {e.response.status_code}: {body}{hint}") from e
            ct = (r.headers.get("content-type") or "").lower()
            try:
                data = r.json()
            except json.JSONDecodeError:
                snippet = (r.text or "")[:400].replace("\n", " ")
                raise RuntimeError(
                    f"SearXNG não devolveu JSON (Content-Type: {ct or '?'}). "
                    f"Confirme GET {search_url}?q=teste&format=json no browser. Trecho: {snippet!r}"
                ) from None
    except httpx.RequestError as e:
        raise RuntimeError(
            f"SearXNG inacessível ({type(e).__name__}: {e}). "
            f"URL usada: {search_url}. Rede, firewall, URL errada ou SEARXNG_SSL_VERIFY=0 se certificado inválido."
        ) from e
    raw = data.get("results") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raw = []
    out: list[dict[str, str]] = []
    for it in raw[:n]:
        if not isinstance(it, dict):
            continue
        trecho = it.get("content") or it.get("snippet") or ""
        out.append(
            {
                "titulo": str(it.get("title") or "")[:500],
                "url": str(it.get("url") or "")[:2000],
                "trecho": str(trecho)[:900],
            }
        )
    return out


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
        try:
            r = client.post(
                url,
                headers={
                    "X-API-KEY": key,
                    "Content-Type": "application/json",
                },
                json={"q": q, "num": n},
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = ""
            try:
                body = (e.response.text or "")[:500]
            except Exception:
                pass
            raise RuntimeError(f"Serper HTTP {e.response.status_code}: {body}") from e
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

    err_searxng: str | None = None
    if _searxng_base_url():
        try:
            res = _searxng_search(q, lim)
            out_sx: dict[str, Any] = {"ok": True, "fonte": "searxng", "query": q, "resultados": res}
            if not res:
                out_sx["aviso"] = (
                    "SearXNG não devolveu resultados. Tente outro termo ou desmarque “Ampliar termo”. "
                    "Confira engines/categorias na sua instância."
                )
            return out_sx
        except Exception as e:
            err_searxng = str(e)

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
            out: dict[str, Any] = {"ok": True, "fonte": "serper", "query": q, "resultados": res}
            if not res:
                out["aviso"] = (
                    "Serper respondeu sem resultados orgânicos. Tente um termo mais curto ou desmarque "
                    "“Ampliar termo” no painel."
                )
            return out
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
            parts = [p for p in (err_searxng, err_brave, err_serper) if p]
            if parts:
                msg = "; ".join(parts) + "; " + msg
            return {"ok": False, "erro": msg}

    parts_err = [p for p in (err_searxng, err_brave, err_serper) if p]
    if parts_err:
        return {
            "ok": False,
            "erro": "Falha na busca: " + "; ".join(parts_err),
        }
    return {
        "ok": False,
        "erro": (
            "Busca web não configurada. Defina SEARXNG_URL (instância SearXNG), ou BRAVE_API_KEY, "
            "ou SERPER_API_KEY (Serper), ou GOOGLE_API_KEY+GOOGLE_CSE_ID (API oficial). "
            "Para Serper em GOOGLE_API_KEY sem CSE: SERPER_USE_GOOGLE_KEY=1."
        ),
    }


def diagnostico_busca() -> dict[str, Any]:
    """JSON para o painel: sem expor chaves, só booleans e caminhos."""
    from pathlib import Path

    env_path = Path(__file__).resolve().parent.parent / ".env"
    gk = bool(os.environ.get("GOOGLE_API_KEY", "").strip())
    cx = bool((os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX") or "").strip())
    sug: list[str] = []
    if not busca_web_configurada():
        if env_path.is_file():
            sug.append("O .env existe: reinicie o terminal após editar (Ctrl+C e python dashboard_server.py).")
            sug.append("Confira: pip install python-dotenv")
        else:
            sug.append("Crie o arquivo .env na raiz (copie de .env.example).")
        if gk and not cx and not bool(os.environ.get("SERPER_USE_GOOGLE_KEY", "").strip()):
            sug.append("Chave em GOOGLE_API_KEY sem CSE: adicione SERPER_USE_GOOGLE_KEY=1 para Serper.")
        if not _searxng_base_url():
            sug.append(
                "Instância SearXNG própria: defina SEARXNG_URL (URL base) e ative format=json no settings.yml."
            )
    sx_base = _searxng_base_url()
    sx_exemplo = None
    if sx_base:
        sx_exemplo = urljoin(sx_base + "/", "search") + "?q=teste&format=json"
    return {
        "busca_web_ativa": busca_web_configurada(),
        "env_arquivo_existe": env_path.is_file(),
        "env_caminho": str(env_path),
        "searxng_url_definido": bool(sx_base),
        "searxng_url_base": sx_base,
        "searxng_teste_no_browser": sx_exemplo,
        "brave_configurado": bool(os.environ.get("BRAVE_API_KEY", "").strip()),
        "serper_api_key_definido": bool(os.environ.get("SERPER_API_KEY", "").strip()),
        "serper_use_google_key": os.environ.get("SERPER_USE_GOOGLE_KEY", "").strip().lower()
        in ("1", "true", "yes", "sim", "on"),
        "google_key_presente": gk,
        "google_cse_presente": cx,
        "serper_chave_resolvida": bool(_serper_key()),
        "sugestoes": sug,
    }
