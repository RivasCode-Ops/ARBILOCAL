"""
Protótipo autônomo (stdlib): mesma lógica do run.py de teste, organizada em gerar_resultado.

Não importa o pacote ARBILOCAL; uso: python arbilocal_proto.py
"""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any

# --- Entrada fixa (protótipo) ---

TAXA_ML = 0.15

precos_mercado = [79.9, 85.0, 89.9, 92.0, 88.5, 84.0]

produto: dict[str, Any] = {"termo": "garrafa termica", "custo": 40}

_CONCORRENCIA_APROVAVEL = frozenset({"BAIXA", "MEDIA"})


def validar_amostra(precos: list[float]) -> str:
    if len(precos) < 5:
        return "BAIXA"
    if max(precos) - min(precos) > 50:
        return "MEDIA"
    return "ALTA"


def calcular_concorrencia(precos: list[float]) -> str:
    if len(precos) > 20:
        return "ALTA"
    if len(precos) > 10:
        return "MEDIA"
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
    if margem >= 30 and concorrencia in _CONCORRENCIA_APROVAVEL and amostra == "ALTA":
        return "APROVAR", ["margem alta", "concorrencia controlada", "amostra confiavel"]
    if margem >= 15:
        return "TESTAR", ["margem media ou risco presente"]
    return "DESCARTAR", ["margem baixa ou risco alto"]


def gerar_resultado(produto: dict[str, Any], precos: list[float]) -> dict[str, Any]:
    """
    Encadeia validação, concorrência, financeiro e decisão.
    Espera produto com chaves 'termo' e 'custo'.
    """
    custo = float(produto["custo"])
    amostra = validar_amostra(precos)
    concorrencia = calcular_concorrencia(precos)
    financeiro = calcular_financeiro(precos, custo)
    decisao, motivos = decidir(financeiro["margem"], concorrencia, amostra)

    return {
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


if __name__ == "__main__":
    resultado = gerar_resultado(produto, precos_mercado)
    print(resultado)
