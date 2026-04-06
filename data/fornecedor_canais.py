"""
Canais de custo / fornecimento (abaixo do preço de varejo típico).

Serve para classificar de onde veio o custo usado na análise. Muitos desses atores
permanecem listados na internet mesmo sem estoque imediato — o campo documenta a
referência, não garante disponibilidade.
"""

from __future__ import annotations

# (id estável, rótulo curto para UI e relatórios)
CANAIS_CUSTO: list[tuple[str, str]] = [
    ("nao_informado", "Não informado"),
    ("fabricante", "Fabricante / indústria"),
    ("distribuidor", "Distribuidor"),
    ("atacadista", "Atacadista"),
    ("atacarejo", "Atacarejo"),
    ("importador", "Importador / trading"),
    ("marketplace_b2b", "Marketplace B2B (ex.: Alibaba, 1688)"),
    ("atacado_online", "Atacado online (site do atacadista)"),
    ("varejo_promocional", "Varejo com promoção / queima"),
    ("outlet_liquidacao", "Outlet / liquidação"),
    ("dropshipping_fornecedor", "Fornecedor para revenda / dropshipping"),
    ("outro", "Outro canal abaixo do varejo cheio"),
]

NOTA_LISTAGEM_ONLINE = (
    "Custo referente ao canal indicado. Fabricantes, distribuidores, atacadistas e similares "
    "costumam permanecer descritos e listados na rede mesmo sem produto disponível no momento; "
    "confirme preço atual e estoque antes de comprar."
)


def canais_para_api() -> list[dict[str, str]]:
    return [{"id": cid, "label": lab} for cid, lab in CANAIS_CUSTO]


def rotulo_canal(canal_id: str) -> str:
    for cid, lab in CANAIS_CUSTO:
        if cid == canal_id:
            return lab
    return canal_id


def normalizar_canal(val: object | None) -> str:
    if val is None:
        return "nao_informado"
    s = str(val).strip().lower().replace(" ", "_").replace("-", "_")
    if not s:
        return "nao_informado"
    ids = {c[0] for c in CANAIS_CUSTO}
    if s in ids:
        return s
    return "outro"
