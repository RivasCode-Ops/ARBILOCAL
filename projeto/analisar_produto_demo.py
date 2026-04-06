"""Demo legado: analisar_produto com dicionário fixo.

Para testar o fluxo atual (main.py, pf, turbo, proto), use na raiz do repo:
  python demo.py

Rodar este arquivo (a partir da raiz):
  python projeto/analisar_produto_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.analise_produto import analisar_produto

produto_teste = {
    "nome": "Garrafa térmica",
    "fornecedor": 8,
    "demanda": 9,
    "margem": 7,
    "concorrencia": 6,
    "logistica": 8,
    "apelo": 7,
    "custo_produto": 30,
    "frete": 12,
    "imposto": 8,
    "taxa": 10,
    "marketing": 5,
    "perdas": 3,
    "preco_venda": 89.90,
}

if __name__ == "__main__":
    analisar_produto(produto_teste)
