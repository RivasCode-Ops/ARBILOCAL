"""
Pipeline operacional (ordem fixa). Nem todas as etapas estão automatizadas no código;
use como contrato de produto e checklist.

Mapeamento aproximado ao repositório:
  buscar_produto      → MercadoLivreClient / JSON / ml_simulado (protocolo_sim)
  filtrar_fornecedor  → manual ou futuro (score fornecedor / parceiros)
  validar_mercado     → validar_mercado_br (data.demanda_br)
  calcular_custo_real → core.calc.calcular_custo_real
  calcular_score      → core.score_composto.calcular_score
  tomar_decisao       → core.decisao_final.decisao_final (escala 0–10)
  testar_aceitacao    → core.modo_teste.modo_teste
  preparar_publicacao → fora do escopo atual
  publicar_venda      → fora do escopo atual
  acompanhar_resultado→ fora do escopo atual
"""

from __future__ import annotations

FLUXO_ETAPAS: tuple[str, ...] = (
    "buscar_produto",
    "filtrar_fornecedor",
    "validar_mercado",
    "calcular_custo_real",
    "calcular_score",
    "tomar_decisao",
    "testar_aceitacao",
    "preparar_publicacao",
    "publicar_venda",
    "acompanhar_resultado",
)

# Alias (mesma sequência imutável)
fluxo = FLUXO_ETAPAS
