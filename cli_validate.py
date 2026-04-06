"""
Subcomando validate (Fase 6): checagens explícitas de JSON ML e de custos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data.aliexpress import get_estimated_cost_brl
from data.mercado_livre import summary_from_search_payload


def validate_ml_json(path: Path) -> list[str]:
    errs: list[str] = []
    if not path.is_file():
        return [f"Arquivo não encontrado: {path}"]
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"JSON inválido: {e.msg} (linha {e.lineno})."]
    if not isinstance(data, dict):
        return ["Raiz do JSON deve ser um objeto."]
    if "results" not in data:
        errs.append("Campo obrigatório ausente: 'results'.")
    elif not isinstance(data["results"], list):
        errs.append("'results' deve ser uma lista.")
    if "paging" in data and not isinstance(data["paging"], dict):
        errs.append("'paging' deve ser um objeto quando presente.")
    if not errs:
        try:
            summary_from_search_payload(data, query="validate", fallback_offset=0)
        except Exception as e:
            errs.append(f"Payload não pôde ser interpretado como busca MLB: {e}")
    return errs


def validate_costs_json(path: Path) -> list[str]:
    if not path.is_file():
        return [f"Arquivo de custos não encontrado: {path}"]
    try:
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Custos JSON inválido: {e.msg} (linha {e.lineno})."]
    if not isinstance(raw, dict):
        return ["Custos: raiz deve ser um objeto (mapa termo → número)."]
    return []


def cmd_validate(argv: list[str] | None) -> int:
    p = argparse.ArgumentParser(prog="main.py validate", description="Valida JSON do ML e/ou arquivo de custos.")
    p.add_argument("--ml-json", type=Path, default=None, help="JSON da rota /sites/MLB/search")
    p.add_argument("--custos", type=Path, default=None, help="Arquivo JSON de custos (padrão: data/aliexpress_costs.json)")
    p.add_argument("--query", type=str, default=None, help="Se definido, verifica se existe custo resolvível para o termo")
    p.add_argument("--custo", type=float, default=None, help="Simula --custo do run (override na checagem de custo)")
    args = p.parse_args(argv)

    if args.ml_json is None and args.custos is None and args.query is None:
        print(
            "Informe ao menos uma opção: --ml-json, --custos ou --query.",
            file=sys.stderr,
        )
        p.print_help(sys.stderr)
        return 5

    errors: list[str] = []
    if args.ml_json is not None:
        errors.extend([f"[ml-json] {x}" for x in validate_ml_json(args.ml_json)])
    custos_path = args.custos
    if args.custos is not None:
        errors.extend([f"[custos] {x}" for x in validate_costs_json(args.custos)])

    if args.query is not None:
        try:
            cost, src = get_estimated_cost_brl(
                args.query,
                manual_override_brl=args.custo,
                costs_file=custos_path,
            )
        except Exception as e:
            errors.append(f"[custo] Configuração inválida: {e}")
            cost = None
            src = None
        if cost is None and src is not None:
            errors.append(
                f"[custo] Nenhum custo resolvido para query={args.query!r} (origem={src.kind}: {src.detail})."
            )

    if errors:
        print("Validação falhou:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 5

    print("Validação OK.")
    return 0
