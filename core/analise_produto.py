"""
Análise consolidada: custo real, lucro, score (0–10) e decisão.
O dict pode misturar eixos do score (`fornecedor`, `demanda`, …) com dados financeiros;
`calcular_score` só usa as chaves de PESOS (ignora `nome`, custos, preço, etc.).
"""

from __future__ import annotations

from typing import Any

from .calc import calcular_custo_real
from .decisao_final import decisao_final
from .score_composto import calcular_score


def analisar_produto(produto: dict[str, Any]) -> dict[str, Any]:
    custo_real = calcular_custo_real(
        float(produto["custo_produto"]),
        frete=float(produto["frete"]),
        imposto=float(produto["imposto"]),
        taxa=float(produto["taxa"]),
        marketing=float(produto["marketing"]),
        perdas=float(produto["perdas"]),
    )
    preco_venda = float(produto["preco_venda"])
    lucro = preco_venda - custo_real
    score = calcular_score(produto)
    decisao = decisao_final(score)

    print("Produto:", produto["nome"])
    print("Custo real:", round(custo_real, 2))
    print("Preço de venda:", round(preco_venda, 2))
    print("Lucro estimado:", round(lucro, 2))
    print("Score:", round(score, 2))
    print("Decisão:", decisao)
    print("-----------------------------")

    return {
        "nome": produto["nome"],
        "custo_real": round(custo_real, 2),
        "preco_venda": round(preco_venda, 2),
        "lucro_estimado": round(lucro, 2),
        "score": round(score, 2),
        "decisao": decisao,
    }
