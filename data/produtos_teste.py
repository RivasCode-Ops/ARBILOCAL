"""
Casos de exemplo: cada eixo 0–10. Passe o dict inteiro a `calcular_score` (`nome` é ignorado).
"""

from __future__ import annotations

PRODUTOS_TESTE: list[dict[str, str | int]] = [
    {
        "nome": "Garrafa térmica",
        "fornecedor": 8,
        "demanda": 9,
        "margem": 7,
        "concorrencia": 6,
        "logistica": 8,
        "apelo": 7,
    },
    {
        "nome": "Fone genérico",
        "fornecedor": 5,
        "demanda": 6,
        "margem": 5,
        "concorrencia": 4,
        "logistica": 7,
        "apelo": 6,
    },
    {
        "nome": "Produto sem apelo",
        "fornecedor": 7,
        "demanda": 3,
        "margem": 6,
        "concorrencia": 5,
        "logistica": 8,
        "apelo": 2,
    },
]
