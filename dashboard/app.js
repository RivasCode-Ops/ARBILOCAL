const $ = (s, el = document) => el.querySelector(s);
const API_KEY_STORAGE = "arbilocal_api_key";

/** Sempre usa a raiz do host (ex.: http://127.0.0.1:8765/api/...), evitando 404 por pasta errada. */
function apiUrl(endpointPath) {
  const p = String(endpointPath).replace(/^\/+/, "");
  return `${window.location.origin}/${p}`;
}

function extraHeaders() {
  const k = ($("#in-api-key")?.value || sessionStorage.getItem(API_KEY_STORAGE) || "").trim();
  if (!k) return {};
  return { "X-ARBILOCAL-Key": k };
}

function fmtPct(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${Number(n).toFixed(2)}%`;
}

async function api(path, opts = {}) {
  const url = /^https?:\/\//i.test(path) ? path : apiUrl(path);
  const r = await fetch(url, {
    headers: {
      Accept: "application/json",
      ...extraHeaders(),
      ...(opts.headers || {}),
    },
    ...opts,
  });
  const ct = (r.headers.get("content-type") || "").toLowerCase();
  const text = await r.text();
  let data = null;
  if (text && ct.includes("json")) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  } else if (text && text.trimStart().startsWith("{")) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (!r.ok) {
    const fromJson = data && (data.erro || data.error);
    if (fromJson) {
      throw new Error(typeof fromJson === "string" ? fromJson : JSON.stringify(data));
    }
    if (ct.includes("text/html") || (text && text.includes("<!DOCTYPE"))) {
      throw new Error(
        `HTTP ${r.status}: a rota da API não existe neste servidor (resposta HTML). ` +
          "Feche processos antigos na porta, rode de novo nesta pasta: python dashboard_server.py " +
          "e abra http://127.0.0.1:8765/ (não use outro servidor só de arquivos estáticos). " +
          "Teste GET /api/health — deve listar post_endpoints com /api/run-analysis."
      );
    }
    const msg = text && text.length < 400 ? text.trim() : `HTTP ${r.status}`;
    throw new Error(msg);
  }
  if (data == null && text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error("Resposta não é JSON válido.");
    }
  }
  return data;
}

function fillCanaisSelect(canais) {
  const sel = $("#run-canal");
  if (!sel) return;
  const list =
    Array.isArray(canais) && canais.length > 0
      ? canais
      : [{ id: "nao_informado", label: "Não informado" }];
  const cur = sel.value;
  sel.innerHTML = "";
  for (const c of list) {
    const o = document.createElement("option");
    o.value = c.id;
    o.textContent = c.label;
    sel.appendChild(o);
  }
  if (cur && list.some((x) => x.id === cur)) sel.value = cur;
}

async function loadState() {
  const st = await api("/api/state");
  fillCanaisSelect(st.canais_custo);
  $("#stat-produtos").textContent = st.produtos_count;
  $("#stat-reports").textContent = st.reports_count;
  $("#stat-precos").textContent =
    st.precos_cache_ok && st.precos_preview
      ? st.precos_preview
      : st.precos_cache_ok
        ? "OK"
        : "—";

  const tb = $("#tbody-produtos");
  tb.innerHTML = "";
  if (!st.produtos.length) {
    tb.innerHTML =
      '<tr><td colspan="4" style="color:var(--muted)">Nenhum produto em data/produtos_salvos.json</td></tr>';
  } else {
    st.produtos.forEach((p, i) => {
      const tr = document.createElement("tr");
      const canalLab = escapeHtml(p.canal_custo_label || "—");
      tr.innerHTML = `<td>${i + 1}</td><td>${escapeHtml(p.termo)}</td><td>${Number(p.custo).toFixed(2)}</td><td style="color:var(--muted);font-size:0.85rem">${canalLab}</td>`;
      tb.appendChild(tr);
    });
  }

  const trb = $("#tbody-reports");
  trb.innerHTML = "";
  if (!st.reports_recent.length) {
    trb.innerHTML =
      '<tr><td colspan="4" style="color:var(--muted)">Nenhum relatório em reports/</td></tr>';
  } else {
    st.reports_recent.forEach((r) => {
      const tr = document.createElement("tr");
      const d = (r.decisao || "").toString();
      tr.innerHTML = `<td>${escapeHtml(r.termo || "")}</td><td>${fmtPct(r.margem)}</td><td><span class="decisao ${d}">${escapeHtml(d)}</span></td><td style="color:var(--muted);font-size:0.8rem">${escapeHtml(r.arquivo || "")}</td>`;
      trb.appendChild(tr);
    });
  }

  $("#pill-conn").textContent = "Servidor local OK";
  $("#pill-conn").classList.add("ok");

  const stBusca = $("#busca-web-status");
  if (stBusca) {
    if (st.busca_web_ativa) {
      stBusca.textContent = "Busca online ativa no servidor (Brave e/ou Google CSE).";
      stBusca.style.color = "var(--good)";
    } else {
      stBusca.textContent =
        "Busca web desligada: defina BRAVE_API_KEY ou GOOGLE_API_KEY + GOOGLE_CSE_ID no ambiente do Python.";
      stBusca.style.color = "var(--warn)";
    }
  }
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function formatRunResult(data) {
  if (!data.ok) return data.erro || JSON.stringify(data);
  const ml = data.mercado_livre || {};
  const calc = data.calculo || {};
  const dec = data.decisao || {};
  const ver = data.veredito || {};
  const canalId = data.canal_custo;
  const canalLinhas =
    canalId && canalId !== "nao_informado"
      ? [
          `Canal de custo: ${data.canal_custo_label || canalId}`,
          ...(data.nota_fornecedor ? [data.nota_fornecedor] : []),
          ``,
        ]
      : [];

  const lines = [
    `Busca: ${data.query}`,
    `Custo (fonte ${data.custo_fonte}): R$ ${Number(calc.cost_brl).toFixed(2)}`,
    ...canalLinhas,
    `--- Mercado Livre (${ml.fonte || "?"}) ---`,
    `Total de resultados: ${ml.total_resultados}`,
    `Amostra: ${ml.amostra_anuncios} anúncios`,
    `Preço médio: R$ ${Number(ml.preco_medio).toFixed(2)}`,
    `Mediana: R$ ${Number(ml.preco_mediano).toFixed(2)}`,
    ``,
    `--- Cálculo ---`,
    `Taxa ML: ${(Number(calc.ml_fee_rate) * 100).toFixed(1)}%`,
    `Taxa estimada: R$ ${Number(calc.fee_amount_brl).toFixed(2)}`,
    `Líquido após taxa: R$ ${Number(calc.net_after_fee_brl).toFixed(2)}`,
    `Lucro: R$ ${Number(calc.profit_brl).toFixed(2)}`,
    `Margem: ${Number(calc.margin_percent).toFixed(2)}%`,
    ``,
    `--- Decisão ---`,
    `Concorrência: ${dec.concorrencia}`,
    `Recomendação: ${dec.recomendacao}`,
    `Motivo: ${dec.motivo}`,
    ``,
    `--- Resultado ---`,
    `${ver.linha || ver.linha_console || ""}`,
    ``,
    data.relatorio_gravado ? `Relatório: ${data.relatorio_gravado}` : "(relatório não gravado)",
  ];
  return lines.join("\n");
}

$("#form-proto").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = $("#out-proto");
  const err = $("#proto-err");
  err.textContent = "";
  out.classList.remove("show");
  out.textContent = "";

  const termo = $("#in-termo").value.trim();
  const custo = parseFloat($("#in-custo").value.replace(",", "."));
  const precosStr = $("#in-precos").value.trim();

  const btn = $("#btn-calc");
  btn.disabled = true;
  $("#card-sim").classList.add("loading");
  try {
    const data = await api("/api/calc-proto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ termo, custo, precos: precosStr }),
    });
    out.textContent = [
      `Termo: ${data.termo}`,
      `Custo: ${Number(data.custo).toFixed(2)}`,
      `Preço médio: ${Number(data.preco_medio).toFixed(2)}`,
      `Mediana: ${Number(data.mediana).toFixed(2)}`,
      `Lucro: ${Number(data.lucro).toFixed(2)}`,
      `Margem: ${Number(data.margem).toFixed(2)}%`,
      `Decisão: ${data.decisao}`,
      `Motivos: ${(data.motivos || []).join("; ")}`,
    ].join("\n");
    out.classList.add("show");
  } catch (x) {
    err.textContent = x.message || String(x);
  } finally {
    btn.disabled = false;
    $("#card-sim").classList.remove("loading");
  }
});

$("#form-run").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = $("#out-run");
  const err = $("#run-err");
  err.textContent = "";
  out.classList.remove("show");
  out.textContent = "";

  const produto = $("#run-produto").value.trim();
  const custoRaw = $("#run-custo").value.trim();
  const taxaRaw = $("#run-taxa").value.trim().replace(",", ".");
  const usePrecos = $("#run-use-precos").checked;
  const precosStr = $("#run-precos").value.trim();
  const mlTotalRaw = $("#run-mltotal").value.trim();
  const salvar = $("#run-salvar").checked;

  let taxa_ml;
  try {
    taxa_ml = parseFloat(taxaRaw || "0.16");
  } catch {
    taxa_ml = NaN;
  }
  if (Number.isNaN(taxa_ml)) {
    err.textContent = "Taxa ML inválida.";
    return;
  }

  const body = {
    produto,
    taxa_ml,
    salvar,
  };
  if (custoRaw) {
    body.custo = parseFloat(custoRaw.replace(",", "."));
    if (Number.isNaN(body.custo) || body.custo < 0) {
      err.textContent = "Custo inválido.";
      return;
    }
  }
  if (usePrecos) {
    if (!precosStr) {
      err.textContent = "Informe os preços ou desmarque “sem chamar a API”.";
      return;
    }
    body.precos = precosStr;
    if (mlTotalRaw) {
      const n = parseInt(mlTotalRaw, 10);
      if (!Number.isNaN(n) && n >= 0) body.ml_total = n;
    }
  }

  const canalSel = $("#run-canal");
  if (canalSel) {
    body.canal_fornecedor = canalSel.value || "nao_informado";
  }

  const btn = $("#btn-run");
  btn.disabled = true;
  $("#card-run").classList.add("loading");
  try {
    const data = await api("/api/run-analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    out.textContent = formatRunResult(data);
    out.classList.add("show");
    if (data.ok) await loadState();
  } catch (x) {
    err.textContent = x.message || String(x);
  } finally {
    btn.disabled = false;
    $("#card-run").classList.remove("loading");
  }
});

$("#run-use-precos").addEventListener("change", () => {
  $("#run-precos-block").hidden = !$("#run-use-precos").checked;
});

const btnBuscaWeb = $("#btn-busca-web");
if (btnBuscaWeb) {
  btnBuscaWeb.addEventListener("click", async () => {
    const errEl = $("#busca-web-err");
    const out = $("#busca-web-resultados");
    errEl.textContent = "";
    out.innerHTML = "";
    const q = $("#busca-q").value.trim();
    if (!q) {
      errEl.textContent = "Digite um termo de busca.";
      return;
    }
    const enr = $("#busca-enriquecer").checked ? "1" : "0";
    const url = `${apiUrl("api/busca-fornecedores")}?q=${encodeURIComponent(q)}&enriquecer=${encodeURIComponent(enr)}&limite=10`;
    $("#card-busca-web").classList.add("loading");
    try {
      const data = await api(url);
      if (!data.ok) {
        errEl.textContent = data.erro || "Falha na busca.";
        return;
      }
      const meta = document.createElement("p");
      meta.className = "hint";
      meta.textContent = `Fonte: ${data.fonte || "?"} · Consulta: ${data.query || ""}`;
      out.appendChild(meta);
      if (data.aviso) {
        const w = document.createElement("p");
        w.className = "hint";
        w.style.color = "var(--warn)";
        w.textContent = data.aviso;
        out.appendChild(w);
      }
      const ul = document.createElement("ul");
      ul.className = "busca-web-lista";
      for (const r of data.resultados || []) {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = r.url && r.url.startsWith("http") ? r.url : "#";
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = r.titulo || r.url || "Abrir";
        li.appendChild(a);
        li.appendChild(document.createElement("br"));
        const span = document.createElement("span");
        span.className = "busca-trecho";
        span.textContent = r.trecho || "";
        li.appendChild(span);
        ul.appendChild(li);
      }
      out.appendChild(ul);
    } catch (x) {
      errEl.textContent =
        (x.message || String(x)) +
        " Dica: após editar o .env, feche e abra de novo o python dashboard_server.py.";
    } finally {
      $("#card-busca-web").classList.remove("loading");
    }
  });
}

const apiKeyInput = $("#in-api-key");
if (apiKeyInput) {
  const saved = sessionStorage.getItem(API_KEY_STORAGE);
  if (saved) apiKeyInput.value = saved;
  apiKeyInput.addEventListener("change", () => {
    const v = apiKeyInput.value.trim();
    if (v) sessionStorage.setItem(API_KEY_STORAGE, v);
    else sessionStorage.removeItem(API_KEY_STORAGE);
  });
}

function mostrarErroConexao(motivo) {
  $("#pill-conn").textContent = "Sem servidor";
  const b = $("#banner-erro");
  b.hidden = false;
  b.innerHTML =
    "<strong>O dashboard precisa do servidor Python rodando.</strong><br><br>" +
    "1) Abra o <strong>Prompt de Comando</strong> ou <strong>PowerShell</strong>.<br>" +
    "2) Vá até a pasta do projeto:<br>" +
    "<code>cd caminho\\para\\ARBILOCAL</code><br>" +
    "3) Execute:<br>" +
    "<code>python dashboard_server.py</code><br><br>" +
    "4) No navegador, use exatamente:<br>" +
    "<code>http://127.0.0.1:8765/</code><br><br>" +
    "<strong>Não</strong> abra o arquivo <code>dashboard\\index.html</code> com duplo clique — aí a página não encontra a API.<br>" +
    "Alternativa sem servidor: abra <code>dashboard\\painel_dirigido.html</code> (dados fixos de demonstração).<br><br>" +
    (motivo ? "<small>Detalhe: " + escapeHtml(motivo) + "</small>" : "");
}

loadState().catch((x) => {
  const msg = x && x.message ? x.message : String(x);
  if (msg === "Failed to fetch" || msg.includes("NetworkError") || msg.includes("fetch")) {
    mostrarErroConexao("rede / servidor desligado");
  } else {
    mostrarErroConexao(msg);
  }
});
