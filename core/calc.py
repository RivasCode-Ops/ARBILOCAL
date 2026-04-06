"""
Cálculo de lucro, margem e preço médio a partir dos dados coletados.
"""

from __future__ import annotations

from dataclasses import dataclass

from data.mercado_livre import MLSearchSummary


@dataclass(frozen=True)
class AnalysisNumbers:
    average_sale_price_brl: float
    median_sale_price_brl: float
    sample_size: int
    cost_brl: float
    ml_fee_rate: float
    fee_amount_brl: float
    net_after_fee_brl: float
    profit_brl: float
    margin_percent: float


def calcular_custo_real(
    produto: float,
    frete: float = 0.0,
    imposto: float = 0.0,
    taxa: float = 0.0,
    marketing: float = 0.0,
    perdas: float = 0.0,
) -> float:
    """
    Custo total estimado em BRL: aquisição + frete + imposto + taxas + marketing + perdas.
    Só soma valores informados; não infere nada.
    """
    total = produto + frete + imposto + taxa + marketing + perdas
    return round(total, 2)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def compute_analysis(
    ml: MLSearchSummary,
    cost_brl: float,
    *,
    ml_fee_rate: float = 0.16,
) -> AnalysisNumbers:
    """
    ml_fee_rate: fração aproximada retida pelo ML (comissão + possíveis custos fixos
    simplificados). Ajuste por categoria conforme sua operação.
    """
    prices = [x.price for x in ml.listings if x.price > 0]
    n = len(prices)
    if n == 0:
        avg = 0.0
        med = 0.0
    else:
        avg = sum(prices) / n
        med = _median(prices)

    # usa média como "preço de venda de referência" para margem
    sale = avg
    fee_amount = sale * ml_fee_rate
    net_after_fee = sale - fee_amount
    profit = net_after_fee - cost_brl
    margin_pct = (profit / sale * 100.0) if sale > 0 else 0.0

    return AnalysisNumbers(
        average_sale_price_brl=round(avg, 2),
        median_sale_price_brl=round(med, 2),
        sample_size=n,
        cost_brl=round(cost_brl, 2),
        ml_fee_rate=ml_fee_rate,
        fee_amount_brl=round(fee_amount, 2),
        net_after_fee_brl=round(net_after_fee, 2),
        profit_brl=round(profit, 2),
        margin_percent=round(margin_pct, 2),
    )
