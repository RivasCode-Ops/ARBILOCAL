"""
Pipeline completo (custo + ML ou preços digitados + cálculo + decisão) para API web.
Não imprime em stdout; retorna dict JSON-serializável.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from core.calc import compute_analysis
from core.report_export import build_report_payload, write_report_json
from core.rules import decide, final_verdict
from data.aliexpress import CostConfigurationError, get_estimated_cost_brl
from data.fornecedor_canais import normalizar_canal, rotulo_canal
from data.mercado_livre import MercadoLivreClient, parse_precos_cli, summary_from_price_list


def run_full_analysis_json(
    query: str,
    *,
    custo_override: float | None,
    ml_fee: float,
    precos_inline: str | None,
    ml_total: int | None,
    save_report: bool,
    reports_dir: Path,
    canal_custo: str | None = None,
) -> dict:
    q = (query or "").strip()
    if not q:
        return {"ok": False, "codigo": 4, "erro": "Produto / termo de busca vazio."}

    canal_id = normalizar_canal(canal_custo)
    canal_label = rotulo_canal(canal_id)

    if not (0 < ml_fee < 1):
        return {"ok": False, "codigo": 4, "erro": "taxa_ml deve ser entre 0 e 1 (ex.: 0.16)."}

    try:
        cost, cost_src = get_estimated_cost_brl(q, manual_override_brl=custo_override)
    except CostConfigurationError as e:
        return {"ok": False, "codigo": 3, "erro": f"Configuração de custo: {e}"}

    if cost is None:
        return {
            "ok": False,
            "codigo": 2,
            "erro": (
                f"Custo não definido para esta busca. Origem: {cost_src.kind} — {cost_src.detail}. "
                "Informe o custo no formulário, defina ALIEXPRESS_COST_BRL ou edite data/aliexpress_costs.json."
            ),
        }

    use_precos = bool(precos_inline and precos_inline.strip())
    try:
        if use_precos:
            pl = parse_precos_cli(precos_inline.strip())
            if not pl:
                return {"ok": False, "codigo": 1, "erro": "Lista de preços vazia."}
            summary = summary_from_price_list(q, pl, total_results=ml_total)
        else:
            summary = MercadoLivreClient().search(q, limit=50)
    except Exception as e:
        return {
            "ok": False,
            "codigo": 1,
            "erro": f"Mercado Livre ou preços: {e}",
        }

    numbers = compute_analysis(summary, cost, ml_fee_rate=ml_fee)
    decision = decide(summary, numbers)
    verdict = final_verdict(decision)

    rel_name: str | None = None
    if save_report:
        reports_dir.mkdir(parents=True, exist_ok=True)
        payload = build_report_payload(
            q,
            numbers,
            decision,
            canal_custo=canal_id,
            canal_custo_label=canal_label,
        )
        out = write_report_json(reports_dir, q, payload)
        rel_name = out.name

    return {
        "ok": True,
        "query": q,
        "canal_custo": canal_id,
        "canal_custo_label": canal_label,
        "nota_fornecedor": (
            "Listagens online não garantem estoque; confirme com o fornecedor."
            if canal_id != "nao_informado"
            else None
        ),
        "custo_fonte": cost_src.kind,
        "custo_detalhe": cost_src.detail,
        "mercado_livre": {
            "total_resultados": summary.total_results,
            "amostra_anuncios": len(summary.listings),
            "preco_medio": numbers.average_sale_price_brl,
            "preco_mediano": numbers.median_sale_price_brl,
            "fonte": "precos_digitados" if use_precos else "api_mlb",
        },
        "calculo": asdict(numbers),
        "decisao": {
            "concorrencia": decision.competition.value,
            "recomendacao": decision.recommendation.value,
            "motivo": decision.reason,
        },
        "veredito": {
            "linha": verdict.linha,
            "linha_console": verdict.linha_console,
            "veredito": verdict.veredito,
            "risco": verdict.risco,
        },
        "relatorio_gravado": rel_name,
    }
