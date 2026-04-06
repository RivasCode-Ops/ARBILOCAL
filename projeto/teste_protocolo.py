"""
Testes do protocolo e funções auxiliares (stdlib unittest).

Raiz do repositório = pasta acima de /projeto.

  python projeto/teste_protocolo.py
  python -m unittest projeto.teste_protocolo -v
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SIM_JSON = ROOT / "data" / "ml_simulado.json"
PROTOCOLO = ROOT / "protocolo_sim.py"


class TestCustoReal(unittest.TestCase):
    def test_soma(self) -> None:
        from core.calc import calcular_custo_real

        self.assertEqual(calcular_custo_real(10, frete=5, imposto=2, taxa=1, marketing=1, perdas=1), 20.0)


class TestDecisaoFinal(unittest.TestCase):
    def test_limiar(self) -> None:
        from core.decisao_final import decisao_final

        self.assertEqual(decisao_final(8.0), "APROVAR")
        self.assertEqual(decisao_final(7.9), "TESTAR")
        self.assertEqual(decisao_final(6.0), "TESTAR")
        self.assertEqual(decisao_final(5.9), "DESCARTAR")


class TestScoreComposto(unittest.TestCase):
    def test_pesos_somam_1(self) -> None:
        from core.score_composto import PESOS, calcular_score

        self.assertAlmostEqual(sum(PESOS.values()), 1.0, places=6)
        d = {k: 10.0 for k in PESOS}
        self.assertEqual(calcular_score(d), 10.0)
        d2 = {k: 10 for k in PESOS}
        self.assertEqual(calcular_score(d2), 10.0)

    def test_apelo_incluso(self) -> None:
        from core.score_composto import PESOS

        self.assertIn("apelo", PESOS)


class TestModoTeste(unittest.TestCase):
    def test_regras(self) -> None:
        from core.modo_teste import modo_teste

        self.assertEqual(modo_teste(1, 0), "ESCALAR")
        self.assertEqual(modo_teste(0, 11), "AJUSTAR")
        self.assertEqual(modo_teste(0, 10), "DESCARTAR")


class TestLogisticaApelo(unittest.TestCase):
    def test_logistica(self) -> None:
        from core.score_logistica import score_logistica

        self.assertEqual(score_logistica(5), 10)
        self.assertEqual(score_logistica(15), 7)
        self.assertEqual(score_logistica(30), 4)

    def test_apelo(self) -> None:
        from core.score_apelo import score_apelo

        self.assertEqual(score_apelo(80, 60), 70.0)


class TestFluxo(unittest.TestCase):
    def test_etapas(self) -> None:
        from core.fluxo import FLUXO_ETAPAS

        self.assertEqual(len(FLUXO_ETAPAS), 10)
        self.assertEqual(FLUXO_ETAPAS[0], "buscar_produto")
        self.assertEqual(FLUXO_ETAPAS[-1], "acompanhar_resultado")


class TestPrecosInline(unittest.TestCase):
    def test_parse_precos_cli(self) -> None:
        from data.mercado_livre import parse_precos_cli

        self.assertEqual(parse_precos_cli("79.9,85"), [79.9, 85.0])
        self.assertEqual(parse_precos_cli("79,9; 85 "), [79.9, 85.0])
        self.assertEqual(parse_precos_cli("79.9;85;89.9"), [79.9, 85.0, 89.9])

    def test_summary_from_price_list(self) -> None:
        from core.calc import compute_analysis
        from data.mercado_livre import summary_from_price_list

        s = summary_from_price_list("garrafa", [80.0, 90.0], total_results=100)
        self.assertEqual(s.total_results, 100)
        self.assertEqual(len(s.listings), 2)
        n = compute_analysis(s, 40.0, ml_fee_rate=0.16)
        self.assertEqual(n.sample_size, 2)
        self.assertEqual(n.average_sale_price_brl, 85.0)


class TestMercadoSimulado(unittest.TestCase):
    def test_arquivo_existe(self) -> None:
        self.assertTrue(SIM_JSON.is_file(), f"falta {SIM_JSON}")

    def test_validar_mercado_br_json(self) -> None:
        if not SIM_JSON.is_file():
            self.skipTest("ml_simulado.json ausente")
        from data.demanda_br import validar_mercado_br

        r = validar_mercado_br("teste", ml_json_path=SIM_JSON)
        self.assertEqual(r["fonte"], "mercadolivre_mlb")
        self.assertIn("score_demanda_br", r)
        self.assertGreater(r["score_demanda_br"], 0)


class TestProdutosTeste(unittest.TestCase):
    def test_tres_casos(self) -> None:
        from core.decisao_final import decisao_final
        from core.score_composto import calcular_score
        from data.produtos_teste import PRODUTOS_TESTE

        self.assertEqual(len(PRODUTOS_TESTE), 3)
        for item in PRODUTOS_TESTE:
            nome = item["nome"]
            score = calcular_score(item)
            veredito = decisao_final(score)
            self.assertIsInstance(nome, str)
            self.assertIn(veredito, ("APROVAR", "TESTAR", "DESCARTAR"))
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 10.0)

    def test_garrafa_testar(self) -> None:
        from core.decisao_final import decisao_final
        from core.score_composto import calcular_score
        from data.produtos_teste import PRODUTOS_TESTE

        g = PRODUTOS_TESTE[0]
        score = calcular_score(g)
        self.assertAlmostEqual(score, 7.55, places=2)
        self.assertGreaterEqual(score, 6.0)
        self.assertEqual(decisao_final(score), "TESTAR")

    def test_sem_apelo_descartar(self) -> None:
        from core.decisao_final import decisao_final
        from core.score_composto import calcular_score
        from data.produtos_teste import PRODUTOS_TESTE

        p = PRODUTOS_TESTE[2]
        score = calcular_score(p)
        self.assertAlmostEqual(score, 4.85, places=2)
        self.assertEqual(decisao_final(score), "DESCARTAR")


class TestAnalisarProduto(unittest.TestCase):
    def test_garrafa_resumo(self) -> None:
        from core.analise_produto import analisar_produto
        import io
        from contextlib import redirect_stdout

        p = {
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
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = analisar_produto(p)
        self.assertEqual(out["decisao"], "TESTAR")
        self.assertAlmostEqual(out["score"], 7.55, places=2)
        self.assertEqual(out["custo_real"], 68.0)
        self.assertAlmostEqual(out["lucro_estimado"], 21.9, places=2)


class TestProtocoloSimDemo(unittest.TestCase):
    def test_demo_exit_zero(self) -> None:
        if not PROTOCOLO.is_file():
            self.skipTest("protocolo_sim.py ausente")
        r = subprocess.run(
            [sys.executable, str(PROTOCOLO), "--demo"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)


if __name__ == "__main__":
    unittest.main()
