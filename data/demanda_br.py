"""
Proxy de demanda / atividade de mercado no Brasil via Mercado Livre (site MLB).

Shopee não está integrado: não há API pública estável equivalente à busca do ML no escopo atual.
O score é heurístico (0–100), não previsão de venda — útil como sinal, não como verdade absoluta.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from data.mercado_livre import MercadoLivreClient, MLSearchSummary, load_search_summary_from_json


def score_demanda_br_from_ml(summary: MLSearchSummary) -> float:
    """
    Compõe um score 0–100 a partir de:
    - volume de ofertas (total na busca) — mercado “espesso”
    - tamanho da amostra com preço
    - média de vendidas históricas na amostra (quando o ML expõe sold_quantity)
    """
    n = len(summary.listings)
    tot = max(0, summary.total_results)

    prateleira = min(45.0, 15.0 * math.log10(tot + 1))
    amostra = min(25.0, n * 5.0)

    sold_vals = [x.sold_quantity for x in summary.listings if x.sold_quantity is not None]
    movimento = 0.0
    if sold_vals:
        avg_sold = sum(sold_vals) / len(sold_vals)
        movimento = min(30.0, math.log10(avg_sold + 1) * 10.0)

    return round(min(100.0, prateleira + amostra + movimento), 2)


def validar_mercado_br(
    produto: str,
    *,
    ml_json_path: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Busca evidência no ML (API ou JSON) e devolve score_demanda_br + metadados.
    Shopee: reservado para integração futura (parceiro/API); hoje retorna None.
    """
    q = produto.strip()
    if not q:
        raise ValueError("produto não pode ser vazio")

    if ml_json_path is not None:
        summary = load_search_summary_from_json(ml_json_path, q)
    else:
        summary = MercadoLivreClient().search(q, limit=limit)

    score = score_demanda_br_from_ml(summary)
    return {
        "score_demanda_br": score,
        "fonte": "mercadolivre_mlb",
        "shopee": None,
        "query": summary.query,
        "total_resultados": summary.total_results,
        "amostra_anuncios": len(summary.listings),
    }
