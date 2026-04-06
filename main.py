"""
Fluxo: produto → Mercado Livre (preço venda) → custo (configurável) → cálculo → decisão.

Fase 2: custo resolvido/validado antes da chamada ao ML (fail-fast, sem retry).
Fase 6: subcomandos run | validate | report | proto | proto-interativo | proto-historico | proto-salvar | proto-listar | proto-analisar-salvo | proto-remover | proto-fluxo; flags extras com default neutro.

Códigos de saída: 0 ok, 1 ML, 2 sem custo, 3 configuração de custo inválida, 4 argumento inválido, 5 validate.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from cli_validate import cmd_validate
from data.aliexpress import CostConfigurationError, get_estimated_cost_brl
from data.fornecedor_canais import CANAIS_CUSTO, normalizar_canal, rotulo_canal
from data.mercado_livre import (
    MercadoLivreClient,
    load_search_summary_from_json,
    parse_precos_cli,
    summary_from_price_list,
)
from core.calc import compute_analysis
from core.engine_proto import gerar_resultado
from core.history import append_analysis_jsonl, utc_now_iso
from core.report_export import build_report_payload, write_report_json
from core.rules import decide, final_verdict

SUBCOMMANDS = frozenset({"run", "validate", "report", "proto", "proto-interativo", "proto-historico", "proto-salvar", "proto-listar", "proto-analisar-salvo", "proto-remover", "proto-fluxo"})

aliases = {
    "pf": "proto-fluxo",
    "ph": "proto-historico",
    "pl": "proto-listar",
    "ps": "proto-salvar",
    "pr": "proto-remover",
    "pa": "proto-analisar-salvo",
}


def configure_stdio_utf8() -> None:
    """No Windows, força UTF-8 em stdout/stderr para acentos e emojis no console."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass


def setup_logging(verbose: bool) -> logging.Logger:
    log = logging.getLogger("arbilocal")
    if log.handlers:
        log.setLevel(logging.DEBUG if verbose else logging.INFO)
        return log
    level = logging.DEBUG if verbose else logging.INFO
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    log.addHandler(h)
    log.setLevel(level)
    return log


def run(
    query: str,
    *,
    ml_fee: float,
    cost_override: float | None,
    ml_json_path: Path | None,
    history_path: Path | None,
    logger: logging.Logger | None = None,
    report_dir: Path | None = None,
    precos_list: list[float] | None = None,
    ml_total_results: int | None = None,
) -> int:
    def _log(msg: str, *args_v: object) -> None:
        if logger:
            logger.info(msg, *args_v)

    _log("execucao iniciada query=%r", query)

    try:
        _log("etapa=custo validando")
        cost, cost_src = get_estimated_cost_brl(query, manual_override_brl=cost_override)
    except CostConfigurationError as e:
        if logger:
            logger.error("etapa=custo falha configuracao: %s", e)
        print(f"Erro de configuração de custo: {e}", file=sys.stderr)
        print(
            "Corrija data/aliexpress_costs.json ou a variável ALIEXPRESS_COST_BRL e execute novamente.",
            file=sys.stderr,
        )
        return 3

    if cost is None:
        if logger:
            logger.error(
                "etapa=custo ausente origem=%s detalhe=%s",
                cost_src.kind,
                cost_src.detail,
            )
        print(
            "Custo não definido para esta busca (validação pré-ML).\n"
            f"  Origem: {cost_src.kind} — {cost_src.detail}\n"
            "  Opções: exporte ALIEXPRESS_COST_BRL=99.90 ou edite data/aliexpress_costs.json\n"
            "  Ou use: python main.py \"seu produto\" --custo 99.90",
            file=sys.stderr,
        )
        return 2

    _log("etapa=custo ok fonte=%s", cost_src.kind)

    try:
        _log("etapa=mercado_livre coletando")
        if precos_list is not None:
            summary = summary_from_price_list(
                query, precos_list, total_results=ml_total_results
            )
            _log("etapa=mercado_livre fonte=precos_inline n=%s total=%s", len(precos_list), summary.total_results)
        elif ml_json_path is not None:
            summary = load_search_summary_from_json(ml_json_path, query)
        else:
            summary = MercadoLivreClient().search(query, limit=50)
    except Exception as e:
        if logger:
            logger.error(
                "etapa=mercado_livre falha: %s",
                e,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
        print(f"Erro ao consultar Mercado Livre: {e}", file=sys.stderr)
        print(
            "Dica: em 403, defina ML_ACCESS_TOKEN ou salve a resposta da busca em um .json "
            "e use: python main.py \"termo\" --ml-json arquivo.json --custo ...\n"
            "  Ou use preços locais: python run.py \"termo\" --precos 79.9,85,89.9 --custo ...",
            file=sys.stderr,
        )
        return 1

    _log("etapa=mercado_livre ok total_resultados=%s", summary.total_results)

    _log("etapa=calculo")
    numbers = compute_analysis(summary, cost, ml_fee_rate=ml_fee)
    _log("etapa=decisao")
    decision = decide(summary, numbers)

    print("=== Análise de revenda ===")
    print(f"Busca: {query}")
    print(f"Custo estimado (fonte {cost_src.kind}): R$ {numbers.cost_brl:.2f}")
    print()
    print("--- Mercado Livre ---")
    print(f"Total de resultados (concorrência): {summary.total_results}")
    print(f"Amostra analisada: {numbers.sample_size} anúncios")
    print(f"Preço médio: R$ {numbers.average_sale_price_brl:.2f}")
    print(f"Preço mediano: R$ {numbers.median_sale_price_brl:.2f}")
    print()
    print("--- Cálculo (taxa ML simplificada) ---")
    print(f"Taxa ML usada: {numbers.ml_fee_rate * 100:.1f}%")
    print(f"Taxa estimada: R$ {numbers.fee_amount_brl:.2f}")
    print(f"Líquido após taxa: R$ {numbers.net_after_fee_brl:.2f}")
    print(f"Lucro potencial: R$ {numbers.profit_brl:.2f}")
    print(f"Margem sobre preço médio: {numbers.margin_percent:.2f}%")
    print()
    print("--- Decisão ---")
    print(f"Concorrência: {decision.competition.value}")
    print(f"Recomendação: {decision.recommendation.value}")
    print(f"Motivo: {decision.reason}")
    verdict = final_verdict(decision)
    print()
    print("--- Resultado final ---")
    try:
        print(verdict.linha)
    except UnicodeEncodeError:
        print(verdict.linha_console)

    if history_path is not None:
        record = {
            "ts": utc_now_iso(),
            "query": query,
            "cost_source_kind": cost_src.kind,
            "mercado_livre": {
                "total_results": summary.total_results,
                "sample_listings": len(summary.listings),
            },
            "calculo": asdict(numbers),
            "decisao": {
                "competition": decision.competition.value,
                "recommendation": decision.recommendation.value,
                "reason": decision.reason,
                "veredito": verdict.veredito,
                "risco": verdict.risco,
                "resultado_final": verdict.linha,
                "resultado_final_console": verdict.linha_console,
            },
        }
        append_analysis_jsonl(history_path, record)

    if report_dir is not None:
        payload = build_report_payload(query, numbers, decision)
        out = write_report_json(report_dir, query, payload)
        _log("etapa=relatorio escrito %s", out)
        print()
        print(f"Relatório JSON: {out.resolve()}")

    _log("execucao concluida codigo=0")
    return 0


def _add_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("produto", help="Termo de busca (ex.: fone bluetooth)")
    p.add_argument(
        "--custo",
        type=float,
        default=None,
        help="Custo em BRL (sobrescreve env e JSON). Deve ser >= 0.",
    )
    p.add_argument(
        "--taxa-ml",
        type=float,
        default=0.16,
        help="Fração de taxas ML sobre o preço de venda (padrão 0.16 = 16%%).",
    )
    p.add_argument(
        "--ml-json",
        type=Path,
        default=None,
        help="JSON da rota /sites/MLB/search (evita HTTP; útil se a API bloquear sua rede).",
    )
    p.add_argument(
        "--precos",
        type=str,
        default=None,
        metavar="LISTA",
        help="Preços da amostra separados por vírgula (ex.: 79.9,85,89.9). Não usa HTTP. Incompatível com --ml-json.",
    )
    p.add_argument(
        "--ml-total",
        type=int,
        default=None,
        metavar="N",
        help="Com --precos: total de resultados MLB para concorrência (padrão: tamanho da lista).",
    )
    p.add_argument(
        "--historico",
        type=Path,
        default=None,
        help="Se definido, acrescenta um registro JSON (uma linha) neste arquivo após sucesso.",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Grava report_<timestamp>_<produto>.json neste diretório (legado e subcomando run).",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Log DEBUG no stderr (subcomandos usam INFO por padrão).")


def _invoke_run(
    args: argparse.Namespace,
    *,
    default_report_dir: Path | None,
    emit_log: bool,
) -> int:
    if args.custo is not None and args.custo < 0:
        print("--custo não pode ser negativo.", file=sys.stderr)
        return 4

    if args.ml_json is not None and args.precos is not None:
        print("Use apenas um de: --ml-json ou --precos.", file=sys.stderr)
        return 4

    if args.ml_total is not None and args.precos is None:
        print("--ml-total só faz sentido com --precos.", file=sys.stderr)
        return 4

    precos_list: list[float] | None = None
    if args.precos is not None:
        try:
            precos_list = parse_precos_cli(args.precos)
        except ValueError as e:
            print(f"--precos inválido: {e}", file=sys.stderr)
            return 4

    log = setup_logging(args.verbose) if emit_log else None
    report_dir = args.report_dir if args.report_dir is not None else default_report_dir

    return run(
        args.produto,
        ml_fee=args.taxa_ml,
        cost_override=args.custo,
        ml_json_path=args.ml_json,
        history_path=args.historico,
        logger=log,
        report_dir=report_dir,
        precos_list=precos_list,
        ml_total_results=args.ml_total,
    )


def main_cli_run(argv: list[str] | None) -> int:
    p = argparse.ArgumentParser(prog="main.py run", description="Executa análise ponta a ponta.")
    _add_run_args(p)
    args = p.parse_args(argv)
    return _invoke_run(args, default_report_dir=None, emit_log=True)


def main_cli_report(argv: list[str] | None) -> int:
    p = argparse.ArgumentParser(
        prog="main.py report",
        description="Executa análise e grava JSON em reports/ (ou --report-dir).",
    )
    _add_run_args(p)
    args = p.parse_args(argv)
    return _invoke_run(args, default_report_dir=Path("reports"), emit_log=True)


_PROTO_PRECOS_PADRAO: tuple[float, ...] = (79.9, 85.0, 89.9, 92.0, 88.5, 84.0)

_PROTO_JSON_NAME = re.compile(
    r"^proto_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})(?:_(\d+))?\.json$"
)

_PROTO_DATE_OPTION_KEYS = frozenset(
    {
        "inicio",
        "início",
        "fim",
        "desde",
        "ate",
        "até",
        "periodo",
        "período",
        "from",
        "to",
        "dt",
        "datetime",
        "timestamp",
        "daterange",
        "data-inicio",
        "data_inicio",
        "data-fim",
        "data_fim",
        "data-inicial",
        "data-final",
    }
)


def _proto_token_is_date_related(token: str) -> bool:
    """Detecta flags que sugerem filtro ou pesquisa por data (proto é atemporal)."""
    if not token.startswith("-"):
        return False
    head = token.split("=", 1)[0].strip()
    key = head.lstrip("-").lower()
    if key in _PROTO_DATE_OPTION_KEYS:
        return True
    if key == "data" or key.startswith("data-") or key.startswith("data_"):
        return True
    return False


def _imprimir_saida_proto(resultado: dict) -> None:
    """Formata a saída do subcomando proto (o dict resultado não é alterado)."""

    def n2(v: object) -> str:
        return f"{float(v):.2f}"

    r = resultado
    print("ARBILOCAL PROTO")
    print(f"Termo: {r['termo']}")
    print(f"Custo: {n2(r['custo'])}")
    print(f"Preço médio: {n2(r['preco_medio'])}")
    print(f"Mediana: {n2(r['mediana'])}")
    print(f"Taxa: {n2(r['taxa'])}")
    print(f"Valor líquido: {n2(r['valor_liquido'])}")
    print(f"Lucro: {n2(r['lucro'])}")
    print(f"Margem: {n2(r['margem'])}%")
    print(f"Concorrência: {r['concorrencia']}")
    print(f"Qualidade da amostra: {r['qualidade_amostra']}")
    print(f"Decisão: {r['decisao']}")
    print("Motivos:")
    for m in r["motivos"]:
        print(f"- {m}")
    print(f"Timestamp: {r['timestamp']}")


def _proto_arquivo_sort_key(path: Path) -> tuple[datetime, int] | None:
    """Ordenação pelo carimbo no nome do arquivo (mais recente = maior tupla)."""
    m = _PROTO_JSON_NAME.match(path.name)
    if not m:
        return None
    d_s, t_s, suf_s = m.group(1), m.group(2), m.group(3)
    try:
        dt = datetime.strptime(f"{d_s}_{t_s}", "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None
    suf = int(suf_s) if suf_s else 0
    return (dt, suf)


def _proto_carregar_json_comparavel(path: Path) -> dict | None:
    """Lê proto_*.json; retorna dict só se tiver margem, lucro e decisao utilizáveis."""
    try:
        with path.open(encoding="utf-8") as f:
            prev = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(prev, dict):
        return None
    try:
        float(prev["margem"])
        float(prev["lucro"])
        str(prev["decisao"])
    except (KeyError, TypeError, ValueError):
        return None
    return prev


def _comparar_proto_com_ultimo_salvo(resultado: dict, path_salvo: Path) -> None:
    """Compara com o proto_*.json anterior mais recente (ignora o recém-salvo e JSONs inválidos)."""
    reports_dir = path_salvo.parent
    if not reports_dir.is_dir():
        print("Primeira execução registrada")
        return

    ordenados: list[tuple[tuple[datetime, int], Path]] = []
    for p in reports_dir.glob("proto_*.json"):
        if not p.is_file():
            continue
        key = _proto_arquivo_sort_key(p)
        if key is None:
            continue
        ordenados.append((key, p))

    if not ordenados:
        print("Primeira execução registrada")
        return

    ordenados.sort(key=lambda x: x[0], reverse=True)
    paths = [p for _, p in ordenados]
    salvo_res = path_salvo.resolve()
    try:
        idx = next(i for i, p in enumerate(paths) if p.resolve() == salvo_res)
    except StopIteration:
        print("Primeira execução registrada")
        return

    prev: dict | None = None
    for j in range(idx + 1, len(paths)):
        cand = _proto_carregar_json_comparavel(paths[j])
        if cand is not None:
            prev = cand
            break

    if prev is None:
        print("Primeira execução registrada")
        return

    try:
        m_atu = float(resultado["margem"])
        m_ant = float(prev["margem"])
        l_atu = float(resultado["lucro"])
        l_ant = float(prev["lucro"])
        d_atu = str(resultado["decisao"])
        d_ant = str(prev["decisao"])
    except (KeyError, TypeError, ValueError):
        print("Primeira execução registrada")
        return

    dm = m_atu - m_ant
    dl = l_atu - l_ant
    print()
    print("Comparação com última execução:")
    print(f"- margem: {dm:+.2f}")
    print(f"- lucro: {dl:+.2f}")
    if d_atu == d_ant:
        print(f"- decisão: manteve {d_atu}")
    else:
        print(f"- decisão: mudou de {d_ant} para {d_atu}")


def _gravar_proto_resultado_json(path: Path, resultado: dict) -> Path | None:
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError) as e:
        print(f"Proto: não foi possível salvar o relatório JSON: {e}")
        return None
    return path


def _persistir_proto_resultado(resultado: dict) -> Path | None:
    """Grava o dict resultado em reports/proto_<timestamp>.json (sem sobrescrever). Retorna o path ou None."""
    reports_dir = Path("reports")
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Proto: não foi possível criar a pasta reports: {e}")
        return None

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = reports_dir / f"proto_{stamp}.json"
    n = 0
    while path.exists():
        n += 1
        path = reports_dir / f"proto_{stamp}_{n}.json"

    return _gravar_proto_resultado_json(path, resultado)


def _proto_reservar_caminhos_relatorio_turbo(reports_dir: Path, qtd: int) -> list[Path] | None:
    """Um mkdir + um glob; reserva qtd nomes proto_<stamp>[ _n].json sem exists() por iteração."""
    if qtd <= 0:
        return []
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Proto: não foi possível criar a pasta reports: {e}")
        return None
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base = f"proto_{stamp}"
    ocupados: set[int] = set()
    for p in reports_dir.glob(f"{base}*.json"):
        if p.name == f"{base}.json":
            ocupados.add(0)
        else:
            m = re.match(rf"^{re.escape(base)}_(\d+)\.json$", p.name)
            if m:
                ocupados.add(int(m.group(1)))
    paths: list[Path] = []
    slot = 0
    while len(paths) < qtd:
        if slot not in ocupados:
            ocupados.add(slot)
            if slot == 0:
                paths.append(reports_dir / f"{base}.json")
            else:
                paths.append(reports_dir / f"{base}_{slot}.json")
        slot += 1
        if slot > 10**6:
            return None
    return paths


def main_cli_proto(argv: list[str] | None) -> int:
    """core.engine_proto; sem API, sem banco. Padrões explícitos se --termo/--custo/--precos omitidos."""
    p = argparse.ArgumentParser(
        prog="main.py proto",
        description="Executa o motor de protótipo (preços locais + decisão).",
    )
    p.add_argument(
        "--termo",
        default="garrafa termica",
        help='Rótulo do produto (padrão: "garrafa termica").',
    )
    p.add_argument(
        "--custo",
        type=float,
        default=40.0,
        help="Custo em BRL (padrão: 40).",
    )
    p.add_argument(
        "--precos",
        default=None,
        metavar="LISTA",
        help='Preços separados por vírgula (ex.: "99.9,109.9,119.9"). '
        "Com ponto e vírgula permite decimal com vírgula (ex.: 79,9;85). "
        "Omitido: usa a lista de demonstração (6 preços).",
    )
    args, unknown = p.parse_known_args(argv)
    if unknown:
        if any(_proto_token_is_date_related(u) for u in unknown):
            print("O subcomando proto não aceita datas nem intervalos temporais (motor atemporal).")
            return 4
        print(f"Argumento não reconhecido no subcomando proto: {' '.join(unknown)}")
        return 4

    termo = (args.termo or "").strip()
    if not termo:
        print("Termo inválido")
        return 4

    custo = args.custo
    if not math.isfinite(custo) or custo <= 0:
        print("Custo inválido")
        return 4

    if args.precos is None:
        precos = list(_PROTO_PRECOS_PADRAO)
    else:
        try:
            precos = parse_precos_cli(args.precos)
        except ValueError as e:
            print(f"Erro ao interpretar preços: {e}")
            return 4

    if len(precos) < 3:
        print("Lista de preços inválida")
        return 4
    for preco in precos:
        if preco <= 0 or not math.isfinite(preco):
            print("Lista de preços inválida")
            return 4

    produto = {"termo": termo, "custo": custo}
    resultado = gerar_resultado(produto, precos)
    _imprimir_saida_proto(resultado)
    path_proto = _persistir_proto_resultado(resultado)
    if path_proto is not None:
        _comparar_proto_com_ultimo_salvo(resultado, path_proto)
    # print(resultado)  # debug: dict cru
    return 0


def main_cli_proto_historico(argv: list[str] | None) -> int:
    """Resume execuções proto em reports/proto_*.json (ordem pelo timestamp no nome)."""
    p = argparse.ArgumentParser(
        prog="main.py proto-historico",
        description="Lista e resume execuções do subcomando proto gravadas em reports/.",
    )
    p.parse_args(argv)

    reports_dir = Path("reports")
    if not reports_dir.is_dir():
        print("Nenhuma execução encontrada")
        return 0

    entries: list[tuple[tuple[datetime, int], dict]] = []
    for path in reports_dir.glob("proto_*.json"):
        if not path.is_file():
            continue
        key = _proto_arquivo_sort_key(path)
        if key is None:
            continue
        try:
            with path.open(encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        try:
            float(raw["margem"])
            str(raw["decisao"])
        except (KeyError, TypeError, ValueError):
            continue
        entries.append((key, raw))

    if not entries:
        print("Nenhuma execução encontrada")
        return 0

    entries.sort(key=lambda x: x[0])

    n_aprovar = n_testar = n_descartar = 0
    for _, d in entries:
        dv = str(d["decisao"])
        if dv == "APROVAR":
            n_aprovar += 1
        elif dv == "TESTAR":
            n_testar += 1
        elif dv == "DESCARTAR":
            n_descartar += 1

    margens = [float(d["margem"]) for _, d in entries]
    melhor = max(margens)
    pior = min(margens)
    ultimo = entries[-1][1]

    termo_u = ultimo.get("termo", "(sem termo)")
    if not isinstance(termo_u, str):
        termo_u = str(termo_u)

    print("HISTÓRICO PROTO")
    print()
    print(f"Total de execuções: {len(entries)}")
    print()
    print(f"APROVAR: {n_aprovar}")
    print(f"TESTAR: {n_testar}")
    print(f"DESCARTAR: {n_descartar}")
    print()
    print(f"Melhor margem: {melhor:.2f}")
    print(f"Pior margem: {pior:.2f}")
    print()
    print("Último resultado:")
    print(f"- termo: {termo_u}")
    print(f"- margem: {float(ultimo['margem']):.2f}")
    print(f"- decisão: {str(ultimo['decisao'])}")
    return 0


def main_cli_proto_salvar(argv: list[str] | None) -> int:
    """Acrescenta termo+custo em data/produtos_salvos.json (lista JSON; sem duplicar par termo+custo)."""
    p = argparse.ArgumentParser(
        prog="main.py proto-salvar",
        description="Salva produto (termo e custo) para análise futura.",
    )
    p.add_argument("--termo", required=True, help="Termo do produto (obrigatório).")
    p.add_argument(
        "--custo",
        type=float,
        required=True,
        help="Custo em BRL (obrigatório, deve ser > 0).",
    )
    p.add_argument(
        "--canal",
        default="nao_informado",
        choices=[c[0] for c in CANAIS_CUSTO],
        help="Canal/fornecedor de referência do custo (fabricante, atacadista, etc.).",
    )
    args = p.parse_args(argv)

    termo = (args.termo or "").strip()
    if not termo:
        print("Termo inválido", file=sys.stderr)
        return 4

    custo = args.custo
    if not math.isfinite(custo) or custo <= 0:
        print("Custo inválido", file=sys.stderr)
        return 4

    path = Path("data/produtos_salvos.json")
    items: list = []

    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Erro ao ler {path}: {e}", file=sys.stderr)
            return 1
        stripped = raw.strip()
        if stripped:
            try:
                loaded = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"Erro ao interpretar JSON em {path}: {e}", file=sys.stderr)
                return 1
            if not isinstance(loaded, list):
                print(
                    f"Formato inválido em {path}: esperado um array JSON (lista).",
                    file=sys.stderr,
                )
                return 1
            items = loaded

    canal_id = normalizar_canal(args.canal)

    def _is_duplicate(termo_s: str, custo_f: float, canal_n: str) -> bool:
        for it in items:
            if not isinstance(it, dict):
                continue
            t = it.get("termo")
            c = it.get("custo")
            if not isinstance(t, str):
                continue
            try:
                if t.strip() != termo_s:
                    continue
                if float(c) != float(custo_f):
                    continue
                if normalizar_canal(it.get("canal_custo")) != canal_n:
                    continue
                return True
            except (TypeError, ValueError):
                continue
        return False

    if _is_duplicate(termo, custo, canal_id):
        print("Produto já existe")
        return 0

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Erro ao criar a pasta {path.parent}: {e}", file=sys.stderr)
        return 1

    novo: dict = {"termo": termo, "custo": custo, "canal_custo": canal_id}
    items.append(novo)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError) as e:
        print(f"Erro ao gravar {path}: {e}", file=sys.stderr)
        return 1

    print("Produto salvo com sucesso")
    return 0


def main_cli_proto_listar(argv: list[str] | None) -> int:
    """Lista produtos em data/produtos_salvos.json (somente leitura; exibe ordenado por custo crescente)."""
    p = argparse.ArgumentParser(
        prog="main.py proto-listar",
        description="Lista produtos salvos (termo e custo).",
    )
    p.parse_args(argv)

    path = Path("data/produtos_salvos.json")

    if not path.exists():
        print("Nenhum produto salvo")
        return 0

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Erro ao ler {path}: {e}", file=sys.stderr)
        return 1

    if not raw.strip():
        print("Nenhum produto salvo")
        return 0

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Erro ao interpretar JSON em {path}: {e}", file=sys.stderr)
        return 1

    if not isinstance(loaded, list):
        print(
            f"Formato inválido em {path}: esperado um array JSON (lista).",
            file=sys.stderr,
        )
        return 1

    linhas: list[tuple[str, float, str, str]] = []
    for it in loaded:
        if not isinstance(it, dict):
            continue
        t = it.get("termo")
        if isinstance(t, str):
            termo_s = t
        elif t is None:
            termo_s = ""
        else:
            termo_s = str(t)
        c_raw = it.get("custo")
        try:
            c_f = float(c_raw)
            if not math.isfinite(c_f):
                continue
        except (TypeError, ValueError):
            continue
        cid = normalizar_canal(it.get("canal_custo"))
        linhas.append((termo_s, c_f, f"{c_f:.2f}", rotulo_canal(cid)))

    if not linhas:
        print("Nenhum produto salvo")
        return 0

    linhas.sort(key=lambda row: row[1])

    print("PRODUTOS SALVOS (ordenado por custo)")
    print()
    for i, (termo_s, _c_f, custo_s, canal_lab) in enumerate(linhas, start=1):
        if i > 1:
            print()
        print(f"{i}. termo: {termo_s}")
        print(f"   custo: {custo_s}")
        print(f"   canal: {canal_lab}")
    return 0


def main_cli_proto_analisar_salvo(argv: list[str] | None) -> int:
    """Analisa um item de data/produtos_salvos.json com --precos (motor proto; grava em reports/)."""
    p = argparse.ArgumentParser(
        prog="main.py proto-analisar-salvo",
        description="Roda o motor proto para um produto salvo (índice de proto-listar) e preços informados.",
    )
    p.add_argument(
        "--indice",
        type=int,
        required=True,
        help="Posição na listagem (1 = primeiro), igual a proto-listar.",
    )
    p.add_argument(
        "--precos",
        required=True,
        metavar="LISTA",
        help='Preços separados por vírgula (ex.: "99.9,109.9,119.9"). '
        "Com ponto e vírgula permite decimal com vírgula (ex.: 79,9;85).",
    )
    args = p.parse_args(argv)

    path = Path("data/produtos_salvos.json")

    if not path.exists():
        print("Nenhum produto salvo")
        return 0

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Erro ao ler {path}: {e}", file=sys.stderr)
        return 1

    if not raw.strip():
        print("Nenhum produto salvo")
        return 0

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Erro ao interpretar JSON em {path}: {e}", file=sys.stderr)
        return 1

    if not isinstance(loaded, list):
        print(
            f"Formato inválido em {path}: esperado um array JSON (lista).",
            file=sys.stderr,
        )
        return 1

    validos: list[dict[str, float | str]] = []
    for it in loaded:
        if not isinstance(it, dict):
            continue
        t = it.get("termo")
        if isinstance(t, str):
            termo_s = t
        elif t is None:
            termo_s = ""
        else:
            termo_s = str(t)
        c_raw = it.get("custo")
        try:
            c_f = float(c_raw)
            if not math.isfinite(c_f):
                continue
        except (TypeError, ValueError):
            continue
        validos.append({"termo": termo_s, "custo": c_f})

    if not validos:
        print("Nenhum produto salvo")
        return 0

    indice = args.indice
    if indice < 1 or indice > len(validos):
        print("Índice inválido")
        return 4

    escolhido = validos[indice - 1]
    termo_raw = escolhido["termo"]
    termo = (termo_raw if isinstance(termo_raw, str) else str(termo_raw)).strip()
    custo = float(escolhido["custo"])
    produto = {"termo": termo, "custo": custo}

    try:
        precos = parse_precos_cli(args.precos)
    except ValueError as e:
        print(f"Erro ao interpretar preços: {e}")
        return 4

    if len(precos) < 3:
        print("Lista de preços inválida")
        return 4
    for preco in precos:
        if preco <= 0 or not math.isfinite(preco):
            print("Lista de preços inválida")
            return 4

    resultado = gerar_resultado(produto, precos)
    _imprimir_saida_proto(resultado)
    path_proto = _persistir_proto_resultado(resultado)
    if path_proto is not None:
        _comparar_proto_com_ultimo_salvo(resultado, path_proto)
    return 0


def main_cli_proto_remover(argv: list[str] | None) -> int:
    """Remove um item de data/produtos_salvos.json pelo índice de proto-listar (base 1)."""
    p = argparse.ArgumentParser(
        prog="main.py proto-remover",
        description="Remove um produto salvo (mesmo índice exibido por proto-listar).",
    )
    p.add_argument(
        "--indice",
        type=int,
        required=True,
        help="Posição na listagem (1 = primeiro), igual a proto-listar.",
    )
    args = p.parse_args(argv)

    path = Path("data/produtos_salvos.json")

    if not path.exists():
        print("Nenhum produto salvo")
        return 0

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Erro ao ler {path}: {e}", file=sys.stderr)
        return 1

    if not raw.strip():
        print("Nenhum produto salvo")
        return 0

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Erro ao interpretar JSON em {path}: {e}", file=sys.stderr)
        return 1

    if not isinstance(loaded, list):
        print(
            f"Formato inválido em {path}: esperado um array JSON (lista).",
            file=sys.stderr,
        )
        return 1

    indices_validos: list[int] = []
    for i, it in enumerate(loaded):
        if not isinstance(it, dict):
            continue
        t = it.get("termo")
        if isinstance(t, str):
            termo_s = t
        elif t is None:
            termo_s = ""
        else:
            termo_s = str(t)
        c_raw = it.get("custo")
        try:
            c_f = float(c_raw)
            if not math.isfinite(c_f):
                continue
        except (TypeError, ValueError):
            continue
        indices_validos.append(i)

    if not indices_validos:
        print("Nenhum produto salvo")
        return 0

    indice = args.indice
    if indice < 1 or indice > len(indices_validos):
        print("Índice inválido")
        return 4

    del loaded[indices_validos[indice - 1]]

    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(loaded, f, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError) as e:
        print(f"Erro ao gravar {path}: {e}", file=sys.stderr)
        return 1

    print("Produto removido com sucesso")
    return 0


_PROTO_FLUXO_CACHE_PRECO = Path("data/ultimo_precos.json")


def _proto_fluxo_parse_precos_de_texto(raw: str) -> list[float] | None:
    """Interpreta JSON de lista de preços (mesmas regras do cache em disco)."""
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) < 3:
        return None
    out: list[float] = []
    for x in data:
        try:
            f = float(x)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(f) or f <= 0:
            return None
        out.append(f)
    return out


def _proto_fluxo_carregar_ultimos_precos() -> list[float] | None:
    """Lê cache de preços do proto-fluxo; retorna None se ausente ou inválido."""
    if not _PROTO_FLUXO_CACHE_PRECO.exists():
        return None
    try:
        raw = _PROTO_FLUXO_CACHE_PRECO.read_text(encoding="utf-8")
    except OSError:
        return None
    return _proto_fluxo_parse_precos_de_texto(raw)


def _proto_fluxo_salvar_ultimos_precos(precos: list[float]) -> None:
    try:
        _PROTO_FLUXO_CACHE_PRECO.parent.mkdir(parents=True, exist_ok=True)
        with _PROTO_FLUXO_CACHE_PRECO.open("w", encoding="utf-8") as f:
            json.dump(precos, f, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError):
        pass


def _proto_fluxo_ultimo_produto_na_lista(loaded: list) -> dict[str, float | str] | None:
    """Último item válido no array (ordem de gravação típica: append ao final)."""
    for it in reversed(loaded):
        if not isinstance(it, dict):
            continue
        t = it.get("termo")
        if isinstance(t, str):
            termo_s = t
        elif t is None:
            termo_s = ""
        else:
            termo_s = str(t)
        c_raw = it.get("custo")
        try:
            c_f = float(c_raw)
            if not math.isfinite(c_f):
                continue
        except (TypeError, ValueError):
            continue
        termo = termo_s.strip()
        return {"termo": termo, "custo": float(c_f)}
    return None


def _proto_fluxo_produtos_validos_ordem_arquivo(loaded: list) -> list[dict[str, float | str]]:
    """Todos os itens válidos na ordem do array JSON (do início ao fim)."""
    produtos: list[dict[str, float | str]] = []
    for it in loaded:
        if not isinstance(it, dict):
            continue
        t = it.get("termo")
        if isinstance(t, str):
            termo_s = t
        elif t is None:
            termo_s = ""
        else:
            termo_s = str(t)
        c_raw = it.get("custo")
        try:
            c_f = float(c_raw)
            if not math.isfinite(c_f):
                continue
        except (TypeError, ValueError):
            continue
        termo = termo_s.strip()
        produtos.append({"termo": termo, "custo": float(c_f)})
    return produtos


def main_cli_proto_fluxo(
    argv: list[str] | None,
    *,
    msg_sem_dados_rapido: str | None = None,
) -> int:
    """Lista produtos salvos (como proto-listar), pede índice e preços, roda proto e grava em reports/."""
    p = argparse.ArgumentParser(
        prog="main.py proto-fluxo",
        description="Fluxo interativo: escolher produto salvo, informar preços, ver resultado proto.",
    )
    p.add_argument(
        "--rapido",
        action="store_true",
        help="Usa o último produto em produtos_salvos.json e últimos preços em ultimo_precos.json, sem prompts.",
    )
    p.add_argument(
        "--turbo",
        action="store_true",
        help="Analisa todos os produtos salvos com os últimos preços; uma linha resumida por item; grava reports/.",
    )
    p.add_argument(
        "--so-aprovados",
        action="store_true",
        help="Com --turbo: imprime só linhas com decisão APROVAR (grava reports/ exceto com --ultra).",
    )
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        metavar="N",
        help="Com --turbo: analisa só os N produtos com menor custo (inteiro > 0).",
    )
    p.add_argument(
        "--ultra",
        action="store_true",
        help="Com --turbo: não grava em reports/; só leitura inicial + resumo no console.",
    )
    args = p.parse_args(argv)

    if args.turbo:
        path_salvos = Path("data/produtos_salvos.json")
        if not path_salvos.exists() or not _PROTO_FLUXO_CACHE_PRECO.exists():
            print("Dados insuficientes para modo turbo")
            return 4
        try:
            raw_s = path_salvos.read_text(encoding="utf-8")
        except OSError:
            print("Dados insuficientes para modo turbo")
            return 4
        if not raw_s.strip():
            print("Dados insuficientes para modo turbo")
            return 4
        try:
            loaded_s = json.loads(raw_s)
        except json.JSONDecodeError:
            print("Dados insuficientes para modo turbo")
            return 4
        if not isinstance(loaded_s, list):
            print("Dados insuficientes para modo turbo")
            return 4
        produtos = _proto_fluxo_produtos_validos_ordem_arquivo(loaded_s)
        try:
            raw_precos = _PROTO_FLUXO_CACHE_PRECO.read_text(encoding="utf-8")
        except OSError:
            print("Dados insuficientes para modo turbo")
            return 4
        precos = _proto_fluxo_parse_precos_de_texto(raw_precos)
        if not produtos or precos is None:
            print("Dados insuficientes para modo turbo")
            return 4
        if len(precos) < 3:
            print("Dados insuficientes para modo turbo")
            return 4
        for preco in precos:
            if preco <= 0 or not math.isfinite(preco):
                print("Dados insuficientes para modo turbo")
                return 4
        if args.limite is not None:
            if args.limite <= 0:
                print("Limite inválido")
                return 4
            produtos = sorted(produtos, key=lambda p: float(p["custo"]))[: args.limite]
        if args.ultra:
            titulo = (
                f"RESULTADOS ULTRA ({args.limite} primeiros)"
                if args.limite is not None
                else "RESULTADOS ULTRA"
            )
        else:
            titulo = (
                f"RESULTADOS TURBO ({args.limite} primeiros)"
                if args.limite is not None
                else "RESULTADOS TURBO"
            )
        print(titulo)
        print()
        if args.ultra:
            print("termo | margem | decisão")
            print()
            caminhos_rel: list[Path] | None = None
        else:
            res = _proto_reservar_caminhos_relatorio_turbo(Path("reports"), len(produtos))
            if res is None:
                return 4
            caminhos_rel = res
        mostrou_aprovado = False
        for idx, produto in enumerate(produtos):
            resultado = gerar_resultado(produto, precos)
            m = float(resultado["margem"])
            d = str(resultado["decisao"])
            t = str(resultado["termo"])
            if args.so_aprovados:
                if d == "APROVAR":
                    print(f"{t} | {m:.2f}% | {d}")
                    mostrou_aprovado = True
            else:
                print(f"{t} | {m:.2f}% | {d}")
            if caminhos_rel is not None:
                _gravar_proto_resultado_json(caminhos_rel[idx], resultado)
        if args.so_aprovados and not mostrou_aprovado:
            print("Nenhum produto aprovado")
        return 0

    if args.rapido:
        msg_falha_rapido = (
            msg_sem_dados_rapido
            if msg_sem_dados_rapido is not None
            else "Dados insuficientes para modo rápido"
        )
        path_salvos = Path("data/produtos_salvos.json")
        if not path_salvos.exists():
            print(msg_falha_rapido)
            return 4
        try:
            raw_s = path_salvos.read_text(encoding="utf-8")
        except OSError:
            print(msg_falha_rapido)
            return 4
        if not raw_s.strip():
            print(msg_falha_rapido)
            return 4
        try:
            loaded_s = json.loads(raw_s)
        except json.JSONDecodeError:
            print(msg_falha_rapido)
            return 4
        if not isinstance(loaded_s, list):
            print(msg_falha_rapido)
            return 4
        produto = _proto_fluxo_ultimo_produto_na_lista(loaded_s)
        precos = _proto_fluxo_carregar_ultimos_precos()
        if produto is None or precos is None:
            print(msg_falha_rapido)
            return 4
        if len(precos) < 3:
            print(msg_falha_rapido)
            return 4
        for preco in precos:
            if preco <= 0 or not math.isfinite(preco):
                print(msg_falha_rapido)
                return 4
        _proto_fluxo_salvar_ultimos_precos(precos)
        resultado = gerar_resultado(produto, precos)
        _imprimir_saida_proto(resultado)
        path_proto = _persistir_proto_resultado(resultado)
        if path_proto is not None:
            _comparar_proto_com_ultimo_salvo(resultado, path_proto)
        return 0

    path = Path("data/produtos_salvos.json")

    if not path.exists():
        print("Nenhum produto salvo")
        return 0

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Erro ao ler {path}: {e}", file=sys.stderr)
        return 1

    if not raw.strip():
        print("Nenhum produto salvo")
        return 0

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Erro ao interpretar JSON em {path}: {e}", file=sys.stderr)
        return 1

    if not isinstance(loaded, list):
        print(
            f"Formato inválido em {path}: esperado um array JSON (lista).",
            file=sys.stderr,
        )
        return 1

    linhas: list[tuple[str, float, str]] = []
    for it in loaded:
        if not isinstance(it, dict):
            continue
        t = it.get("termo")
        if isinstance(t, str):
            termo_s = t
        elif t is None:
            termo_s = ""
        else:
            termo_s = str(t)
        c_raw = it.get("custo")
        try:
            c_f = float(c_raw)
            if not math.isfinite(c_f):
                continue
        except (TypeError, ValueError):
            continue
        linhas.append((termo_s, c_f, f"{c_f:.2f}"))

    if not linhas:
        print("Nenhum produto salvo")
        return 0

    linhas.sort(key=lambda row: row[1])

    print("PRODUTOS SALVOS (ordenado por custo)")
    print()
    for i, (termo_s, _c_f, custo_s) in enumerate(linhas, start=1):
        if i > 1:
            print()
        print(f"{i}. termo: {termo_s}")
        print(f"   custo: {custo_s}")

    try:
        linha_i = input("Escolha o índice do produto: ")
    except EOFError:
        print("Não foi possível ler o índice (entrada encerrada).", file=sys.stderr)
        return 4

    try:
        indice = int(linha_i.strip())
    except ValueError:
        print("Índice inválido")
        return 4

    if indice < 1 or indice > len(linhas):
        print("Índice inválido")
        return 4

    termo_s, custo_f, _ = linhas[indice - 1]
    termo = termo_s.strip()
    produto = {"termo": termo, "custo": float(custo_f)}

    precos: list[float] | None = None
    cached = _proto_fluxo_carregar_ultimos_precos()
    if cached is not None:
        precos_txt = ",".join(str(p) for p in cached)
        print(f"Últimos preços usados: {precos_txt}")
        try:
            reutil = input("Deseja reutilizar? (s/n): ")
        except EOFError:
            print("Não foi possível ler a confirmação (entrada encerrada).", file=sys.stderr)
            return 4
        if reutil.strip().lower() == "s":
            precos = list(cached)

    if precos is None:
        try:
            linha_p = input("Informe os preços separados por vírgula: ")
        except EOFError:
            print("Não foi possível ler os preços (entrada encerrada).", file=sys.stderr)
            return 4

        try:
            precos = parse_precos_cli(linha_p.strip())
        except ValueError as e:
            print(f"Erro ao interpretar preços: {e}")
            return 4

    if len(precos) < 3:
        print("Lista de preços inválida")
        return 4
    for preco in precos:
        if preco <= 0 or not math.isfinite(preco):
            print("Lista de preços inválida")
            return 4

    _proto_fluxo_salvar_ultimos_precos(precos)

    resultado = gerar_resultado(produto, precos)
    _imprimir_saida_proto(resultado)
    path_proto = _persistir_proto_resultado(resultado)
    if path_proto is not None:
        _comparar_proto_com_ultimo_salvo(resultado, path_proto)
    return 0


def main_cli_proto_interativo(argv: list[str] | None) -> int:
    """Perguntas no terminal; mesmo motor e saída que o subcomando proto."""
    p = argparse.ArgumentParser(
        prog="main.py proto-interativo",
        description="Análise proto guiada por perguntas (sem parâmetros na linha de comando).",
    )
    p.parse_args(argv)

    def pergunta(msg: str) -> str:
        print(msg)
        try:
            return input("> ")
        except EOFError:
            print("\nEntrada encerrada.", file=sys.stderr)
            raise SystemExit(4) from None

    while True:
        print("ARBILOCAL INTERATIVO")
        print()

        while True:
            descricao = pergunta("Descreva o produto:").strip()
            if descricao:
                break
            print("A descrição do produto não pode estar vazia.")

        while True:
            linha_custo = pergunta("Informe o custo do produto:").strip().replace(",", ".")
            try:
                custo = float(linha_custo)
            except ValueError:
                print("Custo inválido: informe um número maior que zero.")
                continue
            if not math.isfinite(custo) or custo <= 0:
                print("Custo inválido: informe um número maior que zero.")
                continue
            break

        while True:
            linha_precos = pergunta("Informe os preços de mercado separados por vírgula:").strip()
            try:
                precos = parse_precos_cli(linha_precos)
            except ValueError as e:
                print(f"Preços inválidos: {e}")
                continue
            if len(precos) < 3:
                print("Informe pelo menos três preços, todos maiores que zero.")
                continue
            if any(preco <= 0 or not math.isfinite(preco) for preco in precos):
                print("Cada preço deve ser um número maior que zero.")
                continue
            break

        produto = {"termo": descricao, "custo": custo}
        resultado = gerar_resultado(produto, precos)
        _imprimir_saida_proto(resultado)
        path_proto = _persistir_proto_resultado(resultado)
        if path_proto is not None:
            _comparar_proto_com_ultimo_salvo(resultado, path_proto)

        while True:
            try:
                outro = input("Deseja analisar outro produto? (s/n): ")
            except EOFError:
                print("\nEncerrado.")
                return 0
            r = outro.strip().lower()
            if r == "s":
                print()
                break
            if r == "n":
                print("\nEncerrado.")
                return 0
            print('Responda "s" para sim ou "n" para não.')


def legacy_main() -> None:
    p = argparse.ArgumentParser(description="Análise de produto para revenda (ML + custo configurável).")
    _add_run_args(p)
    args = p.parse_args()
    code = _invoke_run(args, default_report_dir=None, emit_log=args.verbose)
    raise SystemExit(code)


def main() -> None:
    configure_stdio_utf8()
    if len(sys.argv) == 1:
        while True:
            try:
                resp = input("Executar última análise automaticamente? (s/n): ")
            except EOFError:
                print("Execução cancelada")
                raise SystemExit(0)
            r = resp.strip().lower()
            if r == "n":
                print("Execução cancelada")
                raise SystemExit(0)
            if r == "s" or r == "":
                raise SystemExit(
                    main_cli_proto_fluxo(
                        ["--rapido"],
                        msg_sem_dados_rapido="Nenhum dado disponível para execução automática",
                    )
                )
    argv = sys.argv[1:]
    if argv and argv[0] in aliases:
        argv = [aliases[argv[0]], *argv[1:]]
    if argv and argv[0] in SUBCOMMANDS:
        cmd = argv[0]
        rest = argv[1:]
        if cmd == "validate":
            raise SystemExit(cmd_validate(rest))
        if cmd == "run":
            raise SystemExit(main_cli_run(rest))
        if cmd == "report":
            raise SystemExit(main_cli_report(rest))
        if cmd == "proto":
            raise SystemExit(main_cli_proto(rest))
        if cmd == "proto-interativo":
            raise SystemExit(main_cli_proto_interativo(rest))
        if cmd == "proto-historico":
            raise SystemExit(main_cli_proto_historico(rest))
        if cmd == "proto-salvar":
            raise SystemExit(main_cli_proto_salvar(rest))
        if cmd == "proto-listar":
            raise SystemExit(main_cli_proto_listar(rest))
        if cmd == "proto-analisar-salvo":
            raise SystemExit(main_cli_proto_analisar_salvo(rest))
        if cmd == "proto-remover":
            raise SystemExit(main_cli_proto_remover(rest))
        if cmd == "proto-fluxo":
            raise SystemExit(main_cli_proto_fluxo(rest))
    legacy_main()


if __name__ == "__main__":
    main()
