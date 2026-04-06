"""
Subscore de logística por prazo (escala 0–10, para combinar com outros eixos).

`risco_atraso` fica na assinatura para evolução futura (ex. penalidade); hoje não altera o resultado.
"""


def score_logistica(prazo: float, risco_atraso: float | None = None) -> int:
    _ = risco_atraso  # reservado: política de atraso / histórico
    if prazo <= 10:
        return 10
    if prazo <= 20:
        return 7
    return 4
