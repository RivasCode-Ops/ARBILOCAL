"""
Relatório JSON estruturado (Fase 6) — montagem do payload e escrita em disco.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core.calc import AnalysisNumbers
from core.rules import CompetitionLevel, Decision, FinalRecommendation, final_verdict
from data.fornecedor_canais import NOTA_LISTAGEM_ONLINE


def _slug_concorrencia(level: CompetitionLevel) -> str:
    return {"baixa": "baixa", "média": "media", "alta": "alta"}[level.value]


def _codigo_recomendacao(rec: FinalRecommendation) -> str:
    return {
        FinalRecommendation.ATTRACTIVE: "COMPRAR",
        FinalRecommendation.VIABLE: "VIAVEL",
        FinalRecommendation.CAUTIOUS: "CAUTELOSO",
        FinalRecommendation.AVOID: "EVITAR",
    }[rec]


def _utc_generated_at_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_report_payload(
    produto: str,
    numbers: AnalysisNumbers,
    decision: Decision,
    *,
    canal_custo: str | None = None,
    canal_custo_label: str | None = None,
) -> dict:
    v = final_verdict(decision)
    payload: dict = {
        "generated_at": _utc_generated_at_z(),
        "produto": produto,
        "preco_medio": numbers.average_sale_price_brl,
        "custo": numbers.cost_brl,
        "lucro": numbers.profit_brl,
        "margem": round(numbers.margin_percent, 2),
        "concorrencia": _slug_concorrencia(decision.competition),
        "recomendacao": _codigo_recomendacao(decision.recommendation),
        "motivo": decision.reason,
        "resultado_final": v.linha,
        "veredito": v.veredito,
        "risco": v.risco,
    }
    if canal_custo and canal_custo != "nao_informado":
        payload["canal_custo"] = canal_custo
        if canal_custo_label:
            payload["canal_custo_label"] = canal_custo_label
        payload["nota_disponibilidade_fornecedor"] = NOTA_LISTAGEM_ONLINE
    return payload


_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def write_report_json(report_dir: Path, produto: str, payload: dict) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    slug = _SAFE_NAME.sub("_", produto.strip())[:48].strip("_") or "produto"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = report_dir / f"report_{ts}_{slug}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
