"""
Cliente da API pública do Mercado Livre (Brasil, site MLB).
Documentação: https://developers.mercadolibre.com.br/pt_br/items-e-buscas

Se receber 403, cadastre um app no portal de desenvolvedores e defina ML_ACCESS_TOKEN
(ou use --ml-json com um JSON salvo da mesma rota, obtido no seu navegador/rede).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ML_API = "https://api.mercadolibre.com"
SITE_BR = "MLB"
DEFAULT_LIMIT = 50
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


@dataclass(frozen=True)
class MLListing:
    id: str
    title: str
    price: float
    currency_id: str
    available_quantity: int | None
    sold_quantity: int | None
    permalink: str | None


@dataclass(frozen=True)
class MLSearchSummary:
    query: str
    listings: tuple[MLListing, ...]
    total_results: int
    limit: int
    offset: int


def summary_from_search_payload(
    data: dict[str, Any],
    query: str,
    *,
    fallback_offset: int = 0,
) -> MLSearchSummary:
    """Interpreta o JSON retornado por GET /sites/MLB/search."""
    results = data.get("results") or []
    paging = data.get("paging") or {}
    total = int(paging.get("total") or 0)

    listings: list[MLListing] = []
    for item in results:
        listings.append(
            MLListing(
                id=str(item.get("id", "")),
                title=str(item.get("title", "")),
                price=float(item.get("price") or 0),
                currency_id=str(item.get("currency_id") or "BRL"),
                available_quantity=item.get("available_quantity"),
                sold_quantity=item.get("sold_quantity"),
                permalink=item.get("permalink"),
            )
        )

    return MLSearchSummary(
        query=query.strip(),
        listings=tuple(listings),
        total_results=total,
        limit=int(paging.get("limit") or len(listings)),
        offset=int(paging.get("offset") or fallback_offset),
    )


def _parse_one_price_token(token: str) -> float:
    t = token.strip().replace(" ", "")
    if not t:
        raise ValueError("token vazio")
    if t.count(",") == 1 and "." not in t:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError as e:
        raise ValueError(f"não é número: {token!r}") from e
    if v <= 0:
        raise ValueError(f"preço deve ser > 0: {v}")
    return v


def parse_precos_cli(s: str) -> list[float]:
    """
    Lista de preços para CLI.

    - Com ``;``: separador de itens; em cada item, vírgula pode ser decimal (ex.: ``79,9;85``).
    - Só vírgulas: separador de itens; use ponto no decimal (ex.: ``79.9,85``).
    """
    raw = s.strip()
    if not raw:
        raise ValueError("string vazia.")
    if ";" in raw:
        chunks = [c.strip() for c in raw.split(";") if c.strip()]
    else:
        chunks = [c.strip() for c in raw.split(",") if c.strip()]
    out = [_parse_one_price_token(c) for c in chunks]
    if not out:
        raise ValueError("nenhum preço válido.")
    return out


def summary_from_price_list(
    query: str,
    prices: list[float],
    *,
    total_results: int | None = None,
) -> MLSearchSummary:
    """Monta MLSearchSummary sintético a partir de uma lista de preços (amostra local)."""
    q = query.strip()
    if not q:
        raise ValueError("query não pode ser vazia")
    if not prices:
        raise ValueError("informe ao menos um preço.")
    listings: list[MLListing] = []
    for i, p in enumerate(prices):
        listings.append(
            MLListing(
                id=f"synthetic-{i}",
                title="",
                price=float(p),
                currency_id="BRL",
                available_quantity=None,
                sold_quantity=None,
                permalink=None,
            )
        )
    n = len(listings)
    tot = int(total_results) if total_results is not None else n
    if tot < n:
        tot = n
    return MLSearchSummary(
        query=q,
        listings=tuple(listings),
        total_results=tot,
        limit=n,
        offset=0,
    )


def load_search_summary_from_json(path: Path, query: str) -> MLSearchSummary:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON do ML deve ser um objeto com 'results' e 'paging'.")
    return summary_from_search_payload(data, query, fallback_offset=0)


class MercadoLivreClient:
    """Busca pública por nome. Token opcional via variável ML_ACCESS_TOKEN."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = dict(DEFAULT_HEADERS)
        token = os.environ.get("ML_ACCESS_TOKEN", "").strip()
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> MLSearchSummary:
        q = query.strip()
        if not q:
            raise ValueError("query não pode ser vazia")

        url = f"{ML_API}/sites/{SITE_BR}/search"
        params: dict[str, Any] = {"q": q, "limit": min(limit, 50), "offset": offset}

        with httpx.Client(timeout=self._timeout, headers=self._headers()) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        if not isinstance(data, dict):
            raise ValueError("Resposta inesperada da API do Mercado Livre.")

        return summary_from_search_payload(data, q, fallback_offset=offset)

    def search_raw(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """JSON bruto da rota de busca (para gravar em arquivo e usar com --ml-json)."""
        q = query.strip()
        if not q:
            raise ValueError("query não pode ser vazia")
        url = f"{ML_API}/sites/{SITE_BR}/search"
        params: dict[str, Any] = {"q": q, "limit": min(limit, 50), "offset": offset}
        with httpx.Client(timeout=self._timeout, headers=self._headers()) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        if not isinstance(data, dict):
            raise ValueError("Resposta inesperada da API do Mercado Livre.")
        return data
