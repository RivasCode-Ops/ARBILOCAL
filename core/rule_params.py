"""
Parâmetros do motor de decisão (Fase 5): valores padrão + override por variáveis de ambiente.
Prefixo: ARBILOCAL_
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class RuleParams:
    min_margin_percent: float
    good_margin_percent: float
    min_profit_brl: float
    competition_low_max_total: int
    competition_medium_max_total: int
    min_sample_listings: int


def load_rule_params() -> RuleParams:
    return RuleParams(
        min_margin_percent=_env_float("ARBILOCAL_MIN_MARGIN_PERCENT", 12.0),
        good_margin_percent=_env_float("ARBILOCAL_GOOD_MARGIN_PERCENT", 25.0),
        min_profit_brl=_env_float("ARBILOCAL_MIN_PROFIT_BRL", 15.0),
        competition_low_max_total=_env_int("ARBILOCAL_COMPETITION_LOW_MAX", 200),
        competition_medium_max_total=_env_int("ARBILOCAL_COMPETITION_MEDIUM_MAX", 2000),
        min_sample_listings=_env_int("ARBILOCAL_MIN_SAMPLE_LISTINGS", 5),
    )
