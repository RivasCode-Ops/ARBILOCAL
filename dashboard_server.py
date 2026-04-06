#!/usr/bin/env python3
"""
Servidor HTTP do dashboard ARBILOCAL: arquivos estáticos + APIs locais.

  python dashboard_server.py

Variáveis de ambiente (opcional):
  ARBILOCAL_HOST          padrão 127.0.0.1; use 0.0.0.0 para aceitar conexões externas
  ARBILOCAL_PORT          padrão 8765
  ARBILOCAL_API_KEY       se definida, exige header X-ARBILOCAL-Key ou Authorization: Bearer
  ARBILOCAL_CORS_ORIGIN   ex.: * ou https://meusite.com (vários separados por vírgula)
  ARBILOCAL_RATE_LIMIT_RUN máximo de POST /api/run-analysis por IP a cada 60s (padrão 30)
  ARBILOCAL_SAVE_REPORTS  1 (padrão) grava report_*.json em reports/; 0 desliga
  ML_ACCESS_TOKEN         token Mercado Livre (evita 403 em algumas redes)
  BRAVE_API_KEY           busca na web (fornecedores) via Brave Search API
  GOOGLE_API_KEY + GOOGLE_CSE_ID  fallback: Google Programmable Search (cx)
  ARBILOCAL_RATE_LIMIT_BUSCA  máx. GET /api/busca-fornecedores por IP / hora (padrão 40)

Abre no navegador: http://127.0.0.1:8765/ (ou host/porta configurados).
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DASH = ROOT / "dashboard"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from core.engine_proto import gerar_resultado  # noqa: E402
from core.run_web import run_full_analysis_json  # noqa: E402
from data.busca_web_fornecedores import (  # noqa: E402
    busca_web_configurada,
    executar_busca_fornecedores,
)
from data.fornecedor_canais import canais_para_api, normalizar_canal, rotulo_canal  # noqa: E402
from data.mercado_livre import parse_precos_cli  # noqa: E402

HOST = os.environ.get("ARBILOCAL_HOST", "127.0.0.1").strip() or "127.0.0.1"
try:
    PORT = int(os.environ.get("ARBILOCAL_PORT", "8765"))
except ValueError:
    PORT = 8765

_rate_lock = Lock()
_rate_by_ip: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW_SEC = 60.0

_rate_busca_lock = Lock()
_rate_busca_by_ip: dict[str, list[float]] = defaultdict(list)
_RATE_BUSCA_WINDOW_SEC = 3600.0


def _rate_max_run() -> int:
    try:
        return max(1, int(os.environ.get("ARBILOCAL_RATE_LIMIT_RUN", "30")))
    except ValueError:
        return 30


def _rate_max_busca() -> int:
    try:
        return max(1, int(os.environ.get("ARBILOCAL_RATE_LIMIT_BUSCA", "40")))
    except ValueError:
        return 40


def _rate_busca_allow(ip: str) -> bool:
    now = time.monotonic()
    mx = _rate_max_busca()
    with _rate_busca_lock:
        ts = _rate_busca_by_ip[ip]
        ts[:] = [t for t in ts if now - t < _RATE_BUSCA_WINDOW_SEC]
        if len(ts) >= mx:
            return False
        ts.append(now)
        return True


def _rate_allow(ip: str) -> bool:
    now = time.monotonic()
    mx = _rate_max_run()
    with _rate_lock:
        ts = _rate_by_ip[ip]
        ts[:] = [t for t in ts if now - t < _RATE_WINDOW_SEC]
        if len(ts) >= mx:
            return False
        ts.append(now)
        return True


def _save_reports_default() -> bool:
    v = os.environ.get("ARBILOCAL_SAVE_REPORTS", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _api_key_configured() -> str:
    return os.environ.get("ARBILOCAL_API_KEY", "").strip()


def _api_key_ok(handler: BaseHTTPRequestHandler) -> bool:
    expected = _api_key_configured()
    if not expected:
        return True
    got = handler.headers.get("X-ARBILOCAL-Key", "").strip()
    if got == expected:
        return True
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        if auth[7:].strip() == expected:
            return True
    return False


def _cors_allow_origin(handler: BaseHTTPRequestHandler) -> str | None:
    raw = os.environ.get("ARBILOCAL_CORS_ORIGIN", "").strip()
    if not raw:
        return None
    origin = (handler.headers.get("Origin") or "").strip()
    if raw == "*":
        return "*"
    allowed = {x.strip() for x in raw.split(",") if x.strip()}
    if origin and origin in allowed:
        return origin
    return None


def _send_cors(handler: BaseHTTPRequestHandler) -> None:
    o = _cors_allow_origin(handler)
    if o:
        handler.send_header("Access-Control-Allow-Origin", o)
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        handler.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-ARBILOCAL-Key, Authorization, Accept",
        )
        handler.send_header("Access-Control-Max-Age", "86400")


def _read_produtos() -> list[dict]:
    p = ROOT / "data" / "produtos_salvos.json"
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        t = it.get("termo")
        termo = t if isinstance(t, str) else ("" if t is None else str(t))
        try:
            c = float(it.get("custo"))
            if not math.isfinite(c):
                continue
        except (TypeError, ValueError):
            continue
        cid = normalizar_canal(it.get("canal_custo"))
        out.append(
            {
                "termo": termo.strip(),
                "custo": c,
                "canal_custo": cid,
                "canal_custo_label": rotulo_canal(cid),
            }
        )
    out.sort(key=lambda x: x["custo"])
    return out


def _read_precos_cache() -> tuple[bool, str | None]:
    p = ROOT / "data" / "ultimo_precos.json"
    if not p.is_file():
        return False, None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False, None
    if not isinstance(raw, list) or len(raw) < 3:
        return False, None
    preview = ", ".join(str(float(x)) for x in raw[:6])
    return True, preview


def _row_proto(fp: Path) -> dict | None:
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(d, dict):
        return None
    try:
        margem = float(d.get("margem", 0))
        decisao = str(d.get("decisao", ""))
        termo = str(d.get("termo", ""))
    except (TypeError, ValueError):
        return None
    return {"termo": termo, "margem": margem, "decisao": decisao, "arquivo": fp.name}


def _row_report(fp: Path) -> dict | None:
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(d, dict):
        return None
    ver = str(d.get("veredito", ""))
    decisao_map = {"APROVADO": "APROVAR", "TESTAR": "TESTAR", "DESCARTAR": "DESCARTAR"}
    decisao = decisao_map.get(ver, ver)
    try:
        margem = float(d.get("margem", 0))
    except (TypeError, ValueError):
        return None
    termo = str(d.get("produto", ""))
    return {"termo": termo, "margem": margem, "decisao": decisao, "arquivo": fp.name}


def _reports_recent(limit: int = 25) -> list[dict]:
    rd = ROOT / "reports"
    if not rd.is_dir():
        return []
    scored: list[tuple[float, dict]] = []
    for fp in rd.glob("proto_*.json"):
        row = _row_proto(fp)
        if row:
            scored.append((fp.stat().st_mtime, row))
    for fp in rd.glob("report_*.json"):
        row = _row_report(fp)
        if row:
            scored.append((fp.stat().st_mtime, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]


def _reports_count() -> int:
    rd = ROOT / "reports"
    if not rd.is_dir():
        return 0
    return len(list(rd.glob("proto_*.json"))) + len(list(rd.glob("report_*.json")))


def _json_response(handler: BaseHTTPRequestHandler, data: dict, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    _send_cors(handler)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _normalize_http_path(handler: BaseHTTPRequestHandler) -> str:
    """
    Path canoniço para roteamento. Corrige //api/... (alguns proxies / clientes),
    URI absoluta na linha de requisição e query string em self.path.
    """
    raw = handler.path.split("?", 1)[0].split("#", 1)[0]
    if raw.startswith(("http://", "https://")):
        u = urlparse(raw)
        p = u.path or "/"
    else:
        if raw.startswith("//"):
            raw = "/" + raw.lstrip("/")
        while "//" in raw:
            raw = raw.replace("//", "/")
        u = urlparse(raw)
        p = u.path or "/"
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def _file_response(handler: BaseHTTPRequestHandler, path: Path, ctype: str) -> None:
    if not path.is_file():
        handler.send_error(404)
        return
    data = path.read_bytes()
    handler.send_response(200)
    _send_cors(handler)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} - {fmt % args}")

    def do_OPTIONS(self) -> None:
        p = _normalize_http_path(self)
        if p.startswith("/api/"):
            self.send_response(204)
            _send_cors(self)
            self.end_headers()
        else:
            self.send_error(404)

    def do_GET(self) -> None:
        path = _normalize_http_path(self)

        if path == "/api/health":
            return _json_response(
                self,
                {
                    "ok": True,
                    "service": "arbilocal-dashboard",
                    "api_key_required": bool(_api_key_configured()),
                    "post_endpoints": ["/api/calc-proto", "/api/run-analysis"],
                    "canais_custo": canais_para_api(),
                    "busca_web_ativa": busca_web_configurada(),
                },
            )

        if path == "/api/state":
            produtos = _read_produtos()
            precos_ok, precos_preview = _read_precos_cache()
            return _json_response(
                self,
                {
                    "produtos_count": len(produtos),
                    "produtos": produtos,
                    "reports_count": _reports_count(),
                    "reports_recent": _reports_recent(25),
                    "precos_cache_ok": precos_ok,
                    "precos_preview": precos_preview,
                    "api_key_required": bool(_api_key_configured()),
                    "canais_custo": canais_para_api(),
                    "busca_web_ativa": busca_web_configurada(),
                },
            )

        if path == "/api/busca-fornecedores":
            if not _api_key_ok(self):
                return _json_response(self, {"ok": False, "erro": "API key inválida ou ausente."}, 401)
            ip = self.client_address[0]
            if not _rate_busca_allow(ip):
                return _json_response(
                    self,
                    {"ok": False, "erro": "Limite de buscas por hora. Tente mais tarde."},
                    429,
                )
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q") or [""])[0].strip()
            if not q:
                return _json_response(self, {"ok": False, "erro": "Use ?q=termo do produto"}, 400)
            if len(q) > 220:
                return _json_response(self, {"ok": False, "erro": "Termo muito longo (máx. 220)."}, 400)
            enr_s = (qs.get("enriquecer") or ["1"])[0].strip().lower()
            enriquecer = enr_s not in ("0", "false", "no", "nao", "n")
            try:
                lim = int((qs.get("limite") or ["10"])[0])
            except ValueError:
                lim = 10
            data = executar_busca_fornecedores(q, limit=lim, enriquecer=enriquecer)
            if not data.get("ok"):
                err = (data.get("erro") or "").lower()
                status = 503 if "configurada" in err else 502
                return _json_response(self, data, status)
            return _json_response(self, data, 200)

        if path in ("/", "/index.html"):
            return _file_response(self, DASH / "index.html", "text/html; charset=utf-8")
        if path == "/painel_dirigido.html":
            return _file_response(self, DASH / "painel_dirigido.html", "text/html; charset=utf-8")
        if path == "/style.css":
            return _file_response(self, DASH / "style.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return _file_response(self, DASH / "app.js", "application/javascript; charset=utf-8")

        self.send_error(404)

    def do_POST(self) -> None:
        path = _normalize_http_path(self)

        if path == "/api/calc-proto":
            return self._post_calc_proto()
        if path == "/api/run-analysis":
            return self._post_run_analysis()

        self.log_message("POST 404 path=%r normalized=%r", self.path, path)
        self.send_error(404)

    def _post_calc_proto(self) -> None:
        if not _api_key_ok(self):
            return _json_response(self, {"erro": "API key inválida ou ausente."}, 401)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return _json_response(self, {"erro": "Content-Length inválido"}, 400)
        if length <= 0 or length > 50_000:
            return _json_response(self, {"erro": "Corpo inválido"}, 400)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _json_response(self, {"erro": "JSON inválido"}, 400)

        termo = str(body.get("termo", "")).strip()
        if not termo:
            return _json_response(self, {"erro": "Termo obrigatório"}, 400)
        try:
            custo = float(body.get("custo"))
        except (TypeError, ValueError):
            return _json_response(self, {"erro": "Custo inválido"}, 400)
        if not math.isfinite(custo) or custo <= 0:
            return _json_response(self, {"erro": "Custo deve ser maior que zero"}, 400)

        precos_s = str(body.get("precos", "")).strip()
        try:
            precos = parse_precos_cli(precos_s)
        except ValueError as e:
            return _json_response(self, {"erro": str(e)}, 400)
        if len(precos) < 3:
            return _json_response(self, {"erro": "Informe pelo menos 3 preços"}, 400)
        for pr in precos:
            if pr <= 0 or not math.isfinite(pr):
                return _json_response(self, {"erro": "Cada preço deve ser maior que zero"}, 400)

        produto = {"termo": termo, "custo": custo}
        try:
            r = gerar_resultado(produto, precos)
        except Exception as e:
            return _json_response(self, {"erro": str(e)}, 500)

        out: dict = dict(r)
        out["motivos"] = list(r.get("motivos", []))
        return _json_response(self, out)

    def _post_run_analysis(self) -> None:
        if not _api_key_ok(self):
            return _json_response(self, {"ok": False, "erro": "API key inválida ou ausente."}, 401)
        ip = self.client_address[0]
        if not _rate_allow(ip):
            return _json_response(
                self,
                {"ok": False, "erro": "Muitas requisições. Aguarde um minuto e tente de novo."},
                429,
            )
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return _json_response(self, {"ok": False, "erro": "Content-Length inválido"}, 400)
        if length <= 0 or length > 100_000:
            return _json_response(self, {"ok": False, "erro": "Corpo inválido"}, 400)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _json_response(self, {"ok": False, "erro": "JSON inválido"}, 400)

        produto = str(body.get("produto", "")).strip()
        custo_raw = body.get("custo")
        custo_override: float | None
        if custo_raw is None or custo_raw == "":
            custo_override = None
        else:
            try:
                custo_override = float(custo_raw)
            except (TypeError, ValueError):
                return _json_response(self, {"ok": False, "erro": "Custo inválido"}, 400)
            if not math.isfinite(custo_override) or custo_override < 0:
                return _json_response(self, {"ok": False, "erro": "Custo deve ser >= 0"}, 400)

        try:
            ml_fee = float(body.get("taxa_ml", 0.16))
        except (TypeError, ValueError):
            return _json_response(self, {"ok": False, "erro": "taxa_ml inválida"}, 400)

        precos_opt = body.get("precos")
        precos_str = str(precos_opt).strip() if precos_opt is not None else ""

        ml_total_raw = body.get("ml_total")
        ml_total: int | None
        if ml_total_raw is None or ml_total_raw == "":
            ml_total = None
        else:
            try:
                ml_total = int(ml_total_raw)
            except (TypeError, ValueError):
                return _json_response(self, {"ok": False, "erro": "ml_total inválido"}, 400)

        env_save = _save_reports_default()
        br = body.get("salvar", True)
        if br is False:
            save_report = False
        elif isinstance(br, str) and br.strip().lower() in ("0", "false", "no", "off"):
            save_report = False
        else:
            save_report = env_save

        cr = body.get("canal_fornecedor") or body.get("canal_custo")
        canal_para_run = str(cr).strip() if cr is not None and str(cr).strip() else None

        result = run_full_analysis_json(
            produto,
            custo_override=custo_override,
            ml_fee=ml_fee,
            precos_inline=precos_str if precos_str else None,
            ml_total=ml_total,
            save_report=save_report,
            reports_dir=ROOT / "reports",
            canal_custo=canal_para_run,
        )
        if result.get("ok"):
            return _json_response(self, result, 200)
        codigo = int(result.get("codigo", 0))
        status = 400 if codigo in (2, 3, 4) else 502 if codigo == 1 else 400
        return _json_response(self, result, status)


def main() -> None:
    try:
        server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    except OSError as e:
        print(f"Não foi possível abrir {HOST}:{PORT}: {e}")
        print("Outro programa pode estar usando a porta ou o host é inválido.")
        raise SystemExit(1) from e
    print(f"ARBILOCAL dashboard: http://{HOST}:{PORT}/")
    print("APIs: GET /api/state  GET /api/health  GET /api/busca-fornecedores  POST /api/calc-proto  POST /api/run-analysis")
    if busca_web_configurada():
        print("Busca web fornecedores: ativa (Brave e/ou Google CSE no ambiente).")
    else:
        print("Busca web fornecedores: defina BRAVE_API_KEY ou GOOGLE_API_KEY+GOOGLE_CSE_ID para ativar.")
    if HOST == "0.0.0.0":
        print("Modo 0.0.0.0: aceita conexões de outras máquinas na rede. Proteja com firewall e ARBILOCAL_API_KEY.")
    else:
        print("Somente este host. Para expor na rede: defina ARBILOCAL_HOST=0.0.0.0")
    if _api_key_configured():
        print("API key ativa: envie X-ARBILOCAL-Key ou Authorization: Bearer nos POST /api/*.")
    else:
        print("Dica produção: defina ARBILOCAL_API_KEY para exigir chave nos POST.")
    print("Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    main()
