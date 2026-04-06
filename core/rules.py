"""
Regras de decisão: concorrência e recomendação final.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .calc import AnalysisNumbers
from .rule_params import load_rule_params
from data.mercado_livre import MLSearchSummary


class CompetitionLevel(str, Enum):
    LOW = "baixa"
    MEDIUM = "média"
    HIGH = "alta"


class FinalRecommendation(str, Enum):
    AVOID = "evitar"
    CAUTIOUS = "cauteloso"
    VIABLE = "viável"
    ATTRACTIVE = "muito atrativo"


@dataclass(frozen=True)
class Decision:
    competition: CompetitionLevel
    recommendation: FinalRecommendation
    reason: str


@dataclass(frozen=True)
class FinalVerdict:
    """Apresentação prática derivada só de `decision.recommendation` (não altera regras)."""

    linha: str  # com emoji (JSON / UTF-8)
    linha_console: str  # sem emoji (terminais cp1252 / legado)
    veredito: str  # APROVADO | TESTAR | DESCARTAR
    risco: str  # baixo | medio | alto


def final_verdict(decision: Decision) -> FinalVerdict:
    rec = decision.recommendation
    if rec == FinalRecommendation.AVOID:
        return FinalVerdict(
            linha="❌ DESCARTAR (alto risco)",
            linha_console="[X] DESCARTAR (alto risco)",
            veredito="DESCARTAR",
            risco="alto",
        )
    if rec == FinalRecommendation.ATTRACTIVE:
        return FinalVerdict(
            linha="✅ APROVADO (baixo risco)",
            linha_console="[OK] APROVADO (baixo risco)",
            veredito="APROVADO",
            risco="baixo",
        )
    return FinalVerdict(
        linha="⚠️ TESTAR (médio risco)",
        linha_console="[!] TESTAR (medio risco)",
        veredito="TESTAR",
        risco="medio",
    )


def _competition_from_total(total_results: int, low_max: int, medium_max: int) -> CompetitionLevel:
    if total_results < low_max:
        return CompetitionLevel.LOW
    if total_results < medium_max:
        return CompetitionLevel.MEDIUM
    return CompetitionLevel.HIGH


def decide(ml_summary: MLSearchSummary, numbers: AnalysisNumbers) -> Decision:
    params = load_rule_params()
    comp = _competition_from_total(
        ml_summary.total_results,
        params.competition_low_max_total,
        params.competition_medium_max_total,
    )

    min_margin = params.min_margin_percent
    good_margin = params.good_margin_percent
    min_profit_brl = params.min_profit_brl

    m = numbers.margin_percent
    p = numbers.profit_brl
    sample_ok = numbers.sample_size >= params.min_sample_listings

    reasons: list[str] = []

    if not sample_ok:
        reasons.append("amostra pequena de anúncios com preço; média pode distorcer.")

    if numbers.average_sale_price_brl <= 0:
        return Decision(
            comp,
            FinalRecommendation.AVOID,
            "Sem preços válidos no Mercado Livre para esta busca.",
        )

    if m < 0 or p < 0:
        rec = FinalRecommendation.AVOID
        reasons.append("lucro líquido negativo após taxa estimada e custo.")
    elif m < min_margin or p < min_profit_brl:
        rec = FinalRecommendation.CAUTIOUS
        reasons.append("margem ou lucro abaixo do mínimo sugerido.")
    elif comp == CompetitionLevel.HIGH and m < good_margin:
        rec = FinalRecommendation.CAUTIOUS
        reasons.append("concorrência alta com margem moderada.")
    elif m >= good_margin and p >= min_profit_brl * 2:
        rec = FinalRecommendation.ATTRACTIVE
        reasons.append("margem e lucro confortáveis na referência usada.")
    else:
        rec = FinalRecommendation.VIABLE
        reasons.append("números aceitáveis; valide custo real e anúncios concorrentes.")

    return Decision(comp, rec, " ".join(reasons))
