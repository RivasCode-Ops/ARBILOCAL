"""
Apelo do produto: combinação 50/50 entre impacto visual e clareza de problema resolvido.
Eixos costumam ser 0–100; resultado na mesma escala.
"""


def score_apelo(visual: float, resolve_problema: float) -> float:
    total = (visual * 0.5) + (resolve_problema * 0.5)
    return round(total, 2)
