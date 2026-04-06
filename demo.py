#!/usr/bin/env python3
"""
Demonstração ARBILOCAL.

Por padrão: guia do fluxo REAL (Mercado Livre / JSON de busca / custo), sem dados simulados.

Uso (na raiz do repositório):
  python demo.py                    # só o guia + comandos para copiar
  python demo.py --tentar-run       # executa um run real (rede + config necessários)
  python demo.py --proto-exemplo    # opcional: proto/pf com JSON de exemplo em data/ (protótipo)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

DEMO_PRODUTOS = [
    {"termo": "fone bluetooth", "custo": 55.0, "canal_custo": "atacadista"},
    {"termo": "garrafa termica", "custo": 40.0, "canal_custo": "importador"},
    {"termo": "suporte celular", "custo": 25.0, "canal_custo": "marketplace_b2b"},
]
DEMO_PRECOS = [99.9, 109.9, 119.9, 89.9]


def seed_proto_exemplo() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "produtos_salvos.json").write_text(
        json.dumps(DEMO_PRODUTOS, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (DATA / "ultimo_precos.json").write_text(
        json.dumps(DEMO_PRECOS, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("OK: JSONs de exemplo gravados (apenas para modo --proto-exemplo).\n")


def run_cmd(argv_tail: list[str], *, dry: bool) -> int:
    cmd = [sys.executable, str(ROOT / "main.py"), *argv_tail]
    print("$", " ".join(cmd))
    if dry:
        return 0
    return subprocess.call(cmd, cwd=ROOT)


def guia_real() -> None:
    print("=== ARBILOCAL — demonstração REAL ===\n")
    print(
        "Análise de revenda de verdade usa o subcomando run: "
        "custo configurável + dados do Mercado Livre (HTTP) ou JSON da busca / preços que você colheu.\n"
        "Isso NÃO é o modo proto (protótipo com preços digitados só para testar o motor).\n"
    )
    print("O que você precisa:\n")
    print("  • Custo do produto: --custo 99.90, ou variável ALIEXPRESS_COST_BRL, ou data/aliexpress_costs.json")
    print("  • Mercado: token ML_ACCESS_TOKEN e rede liberada, OU")
    print("    arquivo JSON da rota de busca MLB salvo no PC, com --ml-json")
    print("  • Alternativa ao ML na mesma análise run: --precos \"89.9,95,99\" (preços reais que você anotou)\n")
    print("Comandos para copiar (troque termo, custo e caminhos):\n")
    print('  python main.py run "fone bluetooth" --custo 55')
    print('  python main.py run "fone bluetooth" --custo 55 --ml-json data\\sua_busca_mlb.json')
    print('  python main.py run "fone bluetooth" --custo 55 --precos "89.9,95,99,102"')
    print("\nAjuda completa do run:")
    print("  python main.py run -h\n")
    print("Outros fluxos úteis (também reais no sentido de uso diário):")
    print("  python main.py proto-interativo   # você digita termo, custo e preços de mercado (manual)")
    print("  python main.py report \"produto\" --custo 50   # análise + JSON em reports/")
    print("  dashboard/painel_dirigido.html    # painel 100% estático (dados fixos, sem servidor)")
    print("  python dashboard_server.py        # painel + API (ML, proto) em http://127.0.0.1:8765/")
    print("  abrir_dashboard.bat               # Windows: abre navegador e sobe o servidor")
    print("  abrir_painel_estatico.bat         # Windows: só abre o painel estático no navegador")
    print("  Variáveis úteis no servidor: ARBILOCAL_HOST=0.0.0.0 ARBILOCAL_API_KEY=... ML_ACCESS_TOKEN=...")
    print("  Busca fornecedores na web (dashboard): BRAVE_API_KEY ou GOOGLE_API_KEY + GOOGLE_CSE_ID")
    print()


def demo_proto_exemplo(*, dry: bool) -> int:
    print("=== Modo --proto-exemplo (protótipo / lista salva em data/) ===\n")
    if dry:
        print("# Gravaria produtos_salvos.json + ultimo_precos.json de exemplo\n")
    else:
        seed_proto_exemplo()

    sequencia = [
        ["pl"],
        ["pf", "--turbo", "--ultra", "--limite", "3"],
        ["pf", "--turbo", "--so-aprovados"],
        [
            "proto",
            "--termo",
            "fone bluetooth",
            "--custo",
            "55",
            "--precos",
            "99.9,109.9,119.9",
        ],
    ]
    code = 0
    for tail in sequencia:
        code = run_cmd(tail, dry=dry)
        if code != 0:
            break
        print()
    return code


def _configure_stdio_utf8() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass


def main() -> int:
    _configure_stdio_utf8()
    ap = argparse.ArgumentParser(
        description="Demo ARBILOCAL: por padrão guia do fluxo real (run); --proto-exemplo só se quiser JSON fictício.",
    )
    ap.add_argument(
        "--proto-exemplo",
        action="store_true",
        help="Roda cadeia proto/pf com dados de exemplo (sobrescreve data/produtos_salvos.json e ultimo_precos.json).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Com --proto-exemplo: não grava nem executa; só lista comandos.",
    )
    ap.add_argument(
        "--tentar-run",
        action="store_true",
        help='Executa um run real: python main.py run "fone bluetooth" --custo 55 (depende de ML/config).',
    )
    ap.add_argument(
        "--legado",
        action="store_true",
        help="Roda projeto/analisar_produto_demo.py após o restante (módulo analisar_produto).",
    )
    args = ap.parse_args()

    guia_real()

    code = 0
    if args.proto_exemplo:
        code = demo_proto_exemplo(dry=args.dry_run)

    if args.tentar_run:
        print("--- Tentativa de run real ---\n")
        code = run_cmd(["run", "fone bluetooth", "--custo", "55"], dry=args.dry_run)
        print()

    if args.legado and code == 0 and not args.dry_run:
        print("--- Legado: analisar_produto ---\n")
        code = subprocess.call(
            [sys.executable, str(ROOT / "projeto" / "analisar_produto_demo.py")],
            cwd=ROOT,
        )

    if not args.proto_exemplo and not args.tentar_run:
        print("Para tentar um run de verdade agora:")
        print("  python demo.py --tentar-run\n")
        print("Para o antigo demo com JSON de exemplo (protótipo):")
        print("  python demo.py --proto-exemplo\n")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
