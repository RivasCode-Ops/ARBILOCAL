"""
Veredito a partir de score na escala 0–10 (ex.: score composto 0–100 ÷ 10).
"""


def decisao_final(score: float) -> str:
    if score >= 8:
        return "APROVAR"
    if score >= 6:
        return "TESTAR"
    return "DESCARTAR"
