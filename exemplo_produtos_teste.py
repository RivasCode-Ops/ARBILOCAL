"""Exemplo: score 0–10 + decisao_final — mesmo fluxo do teu pseudocódigo."""

from __future__ import annotations

from core.decisao_final import decisao_final
from core.score_composto import calcular_score
from data.produtos_teste import PRODUTOS_TESTE

if __name__ == "__main__":
    for produto in PRODUTOS_TESTE:
        score = calcular_score(produto)
        decisao = decisao_final(score)
        print(f"Produto: {produto['nome']}")
        print(f"Score: {score:.2f}")
        print(f"Decisão: {decisao}")
        print("-" * 30)
