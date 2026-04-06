"""
Protocolo simplificado com dados de mercado SIMULADOS (JSON local — sem API no início).

Ordem exibida: input → custo real → validação BR (simulada) → score (pesos) → logística
              → apelo → decisão final → modo teste (obrigatório — evita prejuízo real).

Não altera main.run. Uso:
  python protocolo_sim.py --demo
  python protocolo_sim.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.calc import calcular_custo_real, compute_analysis
from core.decisao_final import decisao_final
from core.modo_teste import modo_teste
from core.score_apelo import score_apelo
from core.score_composto import PESOS, calcular_score
from core.score_logistica import score_logistica
from data.demanda_br import validar_mercado_br
from data.mercado_livre import load_search_summary_from_json

ROOT = Path(__file__).resolve().parent
SIM_JSON = ROOT / "data" / "ml_simulado.json"


def _stdio_utf8() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass


def concorrencia_score_0_100(total_resultados: int) -> float:
    """Mais ofertas → menor score (0–100), alinhado à ideia de pressão de mercado."""
    t = max(0, int(total_resultados))
    if t < 200:
        return 85.0
    if t < 2000:
        return 55.0
    return 30.0


def carregar_mercado_simulado(produto: str) -> tuple[object, Path]:
    if not SIM_JSON.is_file():
        raise FileNotFoundError(f"Dados simulados ausentes: {SIM_JSON}")
    summary = load_search_summary_from_json(SIM_JSON, produto)
    return summary, SIM_JSON


def prompt_str(label: str, default: str) -> str:
    s = input(f"{label} [{default}]: ").strip()
    return s if s else default


def prompt_float(label: str, default: float) -> float:
    s = input(f"{label} [{default}]: ").strip()
    if not s:
        return default
    return float(s.replace(",", "."))


def prompt_int(label: str, default: int) -> int:
    s = input(f"{label} [{default}]: ").strip()
    if not s:
        return default
    return int(s)


def executar(*, demo: bool) -> None:
    _stdio_utf8()
    print("=== ARBILOCAL — protocolo simulado (sem API) ===\n")

    # 1) Input do usuário
    print("1) Input do usuário")
    if demo:
        produto = "fone bluetooth demo"
        c_aq = 35.0
        frete = 8.0
        imposto = 2.0
        taxa = 1.0
        marketing = 0.0
        perdas = 2.0
        fornecedor = 65.0
        prazo = 12
        risco_atraso = 20.0
        visual = 70.0
        resolve_problema = 75.0
        vendas_teste = 0
        cliques_teste = 8
        print(f"   (demo) produto={produto!r}, custos e scores padrão\n")
    else:
        produto = prompt_str("Nome / termo do produto", "meu produto")
        c_aq = prompt_float("Custo aquisição (BRL)", 35.0)
        frete = prompt_float("Frete (BRL)", 0.0)
        imposto = prompt_float("Imposto (BRL)", 0.0)
        taxa = prompt_float("Outras taxas (BRL)", 0.0)
        marketing = prompt_float("Marketing alocado (BRL)", 0.0)
        perdas = prompt_float("Perdas estimadas (BRL)", 0.0)
        fornecedor = prompt_float("Score fornecedor 0–100 (estimado)", 60.0)
        prazo = prompt_int("Prazo entrega (dias)", 15)
        risco_atraso = prompt_float("Risco de atraso 0–100 (estimado, ainda não penaliza)", 30.0)
        visual = prompt_float("Apelo visual 0–100", 65.0)
        resolve_problema = prompt_float("Resolve problema 0–100", 70.0)
        print()

    # 2) Cálculo de custo real
    print("2) Cálculo de custo real")
    custo_real = calcular_custo_real(c_aq, frete=frete, imposto=imposto, taxa=taxa, marketing=marketing, perdas=perdas)
    print(f"   custo_real = R$ {custo_real:.2f}\n")

    # Mercado simulado (JSON local — sem API)
    summary, sim_path = carregar_mercado_simulado(produto)
    numbers = compute_analysis(summary, custo_real, ml_fee_rate=0.16)

    # 3) Validação BR — proxy demanda via dados simulados (sem HTTP)
    print("3) Validação BR (mercado simulado)")
    br = validar_mercado_br(produto, ml_json_path=sim_path)
    demanda = float(br["score_demanda_br"])
    print(f"   fonte: {br['fonte']} | arquivo: {sim_path.name}")
    print(f"   score_demanda_br: {demanda:.2f} | total_resultados: {br['total_resultados']}\n")

    concorrencia_100 = concorrencia_score_0_100(summary.total_results)
    margem_pct = max(0.0, min(100.0, numbers.margin_percent))
    apelo_100 = score_apelo(visual, resolve_problema)
    logistica_10 = float(score_logistica(float(prazo), risco_atraso))

    def _e10(x: float) -> float:
        return max(0.0, min(10.0, float(x) / 10.0))

    # 4) Score (eixos 0–10; mesmo peso que calcular_score)
    print("4) Score (com peso)", PESOS)
    dados_score = {
        "fornecedor": _e10(fornecedor),
        "demanda": _e10(demanda),
        "margem": _e10(margem_pct),
        "concorrencia": _e10(concorrencia_100),
        "logistica": logistica_10,
        "apelo": _e10(apelo_100),
    }
    score = calcular_score(dados_score)
    print(f"   brutos→0–10: fornecedor={dados_score['fornecedor']:.2f} demanda={dados_score['demanda']:.2f} margem={dados_score['margem']:.2f}")
    print(f"   concorrencia={dados_score['concorrencia']:.2f} logistica={dados_score['logistica']:.2f} apelo={dados_score['apelo']:.2f}")
    print(f"   score (0–10): {score:.2f}\n")

    # 5) Logística (detalhe; já entrou no score)
    print("5) Logística")
    print(f"   score_logistica (0–10): {logistica_10:.0f} | prazo={prazo} dias\n")

    # 6) Apelo (detalhe; já entrou no score)
    print("6) Apelo do produto")
    print(f"   score_apelo (0–100): {apelo_100:.2f} → eixo {dados_score['apelo']:.2f}/10\n")

    # 7) Decisão final (score já em ~0–10)
    print("7) Decisão final")
    veredito = decisao_final(score)
    print(f"   score {score:.2f}/10 → {veredito}")
    if dados_score["apelo"] < 4.0:
        print("   Atenção: apelo baixo — revise listing e proposta de valor antes de comprar estoque.\n")
    else:
        print()

    # 8) Modo teste — não pular (evita prejuízo real)
    print("8) Modo teste (após piloto — sempre avaliar antes de escalar)")
    if demo:
        print(f"   (demo) vendas={vendas_teste}, cliques={cliques_teste}")
    else:
        vendas_teste = prompt_int("Vendas no teste (unidades)", 0)
        cliques_teste = prompt_int("Cliques no teste", 0)
    modo = modo_teste(vendas_teste, cliques_teste)
    print(f"   modo_teste → {modo}")
    print("\n--- Fim do protocolo ---")


def main() -> None:
    p = argparse.ArgumentParser(description="Protocolo ARBILOCAL com mercado simulado (sem API).")
    p.add_argument("--demo", action="store_true", help="Roda com inputs fixos, sem perguntas")
    args = p.parse_args()
    try:
        executar(demo=args.demo)
    except FileNotFoundError as e:
        print(f"Erro: {e}", file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, EOFError) as e:
        print(f"Entrada inválida ou cancelada: {e}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
