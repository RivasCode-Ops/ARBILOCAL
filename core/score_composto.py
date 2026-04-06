"""
Score composto na escala ~0–10: cada eixo deve estar em 0–10; pesos somam 1,0.
Chaves extra (ex.: `nome`) são ignoradas. Chaves de PESOS ausentes contam como 0.
"""

from __future__ import annotations

PESOS = {
    "fornecedor": 0.15,
    "demanda": 0.20,
    "margem": 0.25,
    "concorrencia": 0.10,
    "logistica": 0.10,
    "apelo": 0.20,
}


def calcular_score(dados: dict[str, float | int | str]) -> float:
    """
    Σ eixo_i * peso_i. Use com decisao_final(score) sem dividir (limiares 8 e 6).
    """
    total = 0.0
    for chave, peso in PESOS.items():
        v = dados.get(chave, 0.0)
        try:
            total += float(v) * peso
        except (TypeError, ValueError):
            total += 0.0
    return round(total, 2)
