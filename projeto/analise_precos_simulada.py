"""
Análise com preços simulados (lista local), taxa ML fixa e decisão por margem/custo.

Margem = (lucro / custo) * 100 (sobre custo, não sobre preço de venda).
Concorrência e qualidade de amostra usam apenas o tamanho/espalhamento da lista.

Rodar na raiz: python projeto/analise_precos_simulada.py
"""

from __future__ import annotations

import statistics
from datetime import datetime

# ===== CONFIG FIXA =====
TAXA_ML = 0.15  # 15%

# ===== DADOS DE TESTE (SIMULA MERCADO LIVRE) =====
precos_mercado = [79.9, 85.0, 89.9, 92.0, 88.5, 84.0]


def validar_amostra(precos: list[float]) -> str:
    if len(precos) < 5:
        return "BAIXA"
    if max(precos) - min(precos) > 50:
        return "MEDIA"
    return "ALTA"


def calcular_concorrencia(precos: list[float]) -> str:
    if len(precos) > 20:
        return "ALTA"
    elif len(precos) > 10:
        return "MEDIA"
    else:
        return "BAIXA"


def calcular_financeiro(precos: list[float], custo: float) -> dict[str, float]:
    media = statistics.mean(precos)
    mediana = statistics.median(precos)
    taxa = media * TAXA_ML
    liquido = media - taxa
    lucro = liquido - custo
    margem = (lucro / custo) * 100 if custo > 0 else 0.0

    return {
        "preco_medio": media,
        "mediana": mediana,
        "taxa": taxa,
        "valor_liquido": liquido,
        "lucro": lucro,
        "margem": margem,
    }


def decidir(margem: float, concorrencia: str, amostra: str) -> tuple[str, list[str]]:
    if margem >= 30 and concorrencia in ["BAIXA", "MEDIA"] and amostra == "ALTA":
        return "APROVAR", ["margem alta", "concorrencia controlada", "amostra confiavel"]

    if margem >= 15:
        return "TESTAR", ["margem media ou risco presente"]

    return "DESCARTAR", ["margem baixa ou risco alto"]


def main() -> dict:
    # ===== ENTRADA (EDITAR AQUI) =====
    produto = {
        "termo": "garrafa termica",
        "custo": 40,
    }

    amostra = validar_amostra(precos_mercado)
    concorrencia = calcular_concorrencia(precos_mercado)
    financeiro = calcular_financeiro(precos_mercado, produto["custo"])
    decisao, motivos = decidir(financeiro["margem"], concorrencia, amostra)

    resultado = {
        "termo": produto["termo"],
        "custo": produto["custo"],
        "preco_medio": financeiro["preco_medio"],
        "mediana": financeiro["mediana"],
        "taxa": financeiro["taxa"],
        "valor_liquido": financeiro["valor_liquido"],
        "lucro": financeiro["lucro"],
        "margem": financeiro["margem"],
        "concorrencia": concorrencia,
        "qualidade_amostra": amostra,
        "decisao": decisao,
        "motivos": motivos,
        "timestamp": str(datetime.now()),
    }
    print(resultado)
    return resultado


if __name__ == "__main__":
    main()
