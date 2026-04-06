"""
Regra pós-teste (anúncio piloto): vendas vs. engajamento mínimo.
Não acoplado ao run().
"""


def modo_teste(vendas: int | float, cliques: int | float) -> str:
    if vendas > 0:
        return "ESCALAR"
    if cliques > 10:
        return "AJUSTAR"
    return "DESCARTAR"
