"""
Custo estimado no AliExpress.

Não há API pública simples e estável. Este módulo evita copiar scrapers frágeis do GitHub
e prioriza fontes explícitas: variável de ambiente, arquivo JSON local ou valor em código
para testes. Para produção, integre um actor pago (ex.: Apify) preenchendo o JSON ou
estendendo AliExpressCostSource.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


ENV_COST_KEY = "ALIEXPRESS_COST_BRL"
DEFAULT_MANUAL_PATH = Path(__file__).resolve().parent / "aliexpress_costs.json"


class CostConfigurationError(Exception):
    """JSON de custos ilegível ou variável de ambiente de custo inválida (falha explícita)."""


@dataclass(frozen=True)
class AliExpressCostSource:
    """De onde veio o custo (auditoria)."""

    kind: str  # "env" | "json" | "override" | "none"
    detail: str


def _load_json_map(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise CostConfigurationError(
            f"Arquivo de custos JSON inválido ({path}): {e.msg} (linha {e.lineno})."
        ) from e
    if not isinstance(raw, dict):
        raise CostConfigurationError(f"Arquivo de custos deve ser um objeto JSON em {path}.")
    out: dict[str, float] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, (int, float)):
            out[k.strip().lower()] = float(v)
    return out


def get_estimated_cost_brl(
    product_query: str,
    *,
    manual_override_brl: float | None = None,
    costs_file: Path | None = None,
) -> tuple[float | None, AliExpressCostSource]:
    """
    Retorna (custo_brl, origem). Ordem: override > env > JSON por keyword > none.

    Se ALIEXPRESS_COST_BRL estiver definida e não for número válido >= 0, levanta
    CostConfigurationError (não mascara com fallback para JSON).
    """
    if manual_override_brl is not None and manual_override_brl >= 0:
        return manual_override_brl, AliExpressCostSource("override", "parâmetro manual_override_brl")

    env = os.environ.get(ENV_COST_KEY)
    if env is not None and env.strip():
        try:
            val = float(env.replace(",", "."))
        except ValueError as e:
            raise CostConfigurationError(
                f"{ENV_COST_KEY} definida mas não numérica: {env!r}."
            ) from e
        if val < 0:
            raise CostConfigurationError(f"{ENV_COST_KEY} não pode ser negativa ({val}).")
        return val, AliExpressCostSource("env", ENV_COST_KEY)

    path = costs_file or DEFAULT_MANUAL_PATH
    key = product_query.strip().lower()
    mapping = _load_json_map(path)
    if key in mapping:
        return mapping[key], AliExpressCostSource("json", str(path))
    for mk, cost in mapping.items():
        if mk in key or key in mk:
            return cost, AliExpressCostSource("json", f"{path} (match: {mk})")

    return None, AliExpressCostSource("none", "defina ALIEXPRESS_COST_BRL ou data/aliexpress_costs.json")
