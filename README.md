# ARBILOCAL

Análise de revenda (Mercado Livre + custo + regras), CLI `main.py`, dashboard local `dashboard_server.py` e busca opcional de fornecedores na web (Brave / Google CSE).

## Requisitos

- Python 3.10+ recomendado
- Dependências: `pip install -r requirements.txt`

## Configuração rápida

1. Copie `data/aliexpress_costs.example.json` para `data/aliexpress_costs.json` e edite os custos, **ou** use `--custo` / variável `ALIEXPRESS_COST_BRL`.
2. Mercado Livre: se receber 403, defina `ML_ACCESS_TOKEN` no ambiente.
3. Busca web no painel — veja a seção abaixo.

### Configurar pesquisa web (fornecedores)

1. Instale dependências: `pip install -r requirements.txt` (inclui `python-dotenv`).
2. Copie o modelo: **`.env.example` → `.env`** na raiz do projeto (no Windows pode usar `configurar_pesquisa.bat`).
3. Edite **`.env`** com **uma** das opções:
   - **Brave (recomendado):** crie uma chave em [Brave Search API](https://api.search.brave.com/) e coloque em `BRAVE_API_KEY=...`
   - **Google CSE:** no [Google Cloud](https://console.cloud.google.com/) ative *Custom Search API* e crie uma API key; em [Programmable Search Engine](https://programmablesearchengine.google.com/) crie um mecanismo e copie o **Search engine ID** (*cx*). Preencha `GOOGLE_API_KEY` e `GOOGLE_CSE_ID` (o seu *cx*, ex.: `703f96ca5e3394ad9`).
4. Verifique: `python scripts/verificar_pesquisa.py` — deve indicar que a pesquisa está OK.
5. Suba o dashboard: `python dashboard_server.py` — no card **Busca na web** o status deve ficar verde.

O servidor carrega automaticamente o arquivo **`.env`** ao iniciar (não commite o `.env`).

### Colocar o ARBILOCAL na internet (online)

O **código** do painel já está no [GitHub](https://github.com/RivasCode-Ops/ARBILOCAL); para **rodar na web** você precisa de um **servidor (VPS, nuvem ou PC acessível)** com Python ou Docker e as **mesmas variáveis** do buscador, definidas no **ambiente** do processo (ou `.env` no servidor).

1. **API do buscador** (obrigatório para o card *Busca na web* funcionar):
   - `BRAVE_API_KEY` **ou** `GOOGLE_API_KEY` + `GOOGLE_CSE_ID`  
   - Crie as chaves nos sites oficiais ([Brave Search API](https://api.search.brave.com/), [Google Cloud](https://console.cloud.google.com/) + [Programmable Search](https://programmablesearchengine.google.com/)).

2. **Aceitar conexões externas** ao painel:
   - `ARBILOCAL_HOST=0.0.0.0`
   - `ARBILOCAL_PORT=8765` (ou a porta que o provedor exigir)

3. **Segurança em produção:** defina `ARBILOCAL_API_KEY` e use a mesma chave no campo **“Chave API”** do dashboard (senão qualquer um pode chamar suas APIs).

4. **HTTPS:** em produção, coloque **Nginx**, **Caddy** ou o proxy do provedor na frente (porta 443) e encaminhe para `127.0.0.1:8765`. Se o site for outro domínio, configure `ARBILOCAL_CORS_ORIGIN` conforme a documentação do `dashboard_server.py`.

5. **Mercado Livre** no painel: `ML_ACCESS_TOKEN` no ambiente do servidor, se a API do ML bloquear.

Exemplo **Docker** na nuvem (substitua as chaves):

```bash
docker build -t arbilocal .
docker run -d -p 8765:8765 \
  -e ARBILOCAL_HOST=0.0.0.0 \
  -e BRAVE_API_KEY=sua_chave_brave \
  -e ARBILOCAL_API_KEY=uma_senha_forte \
  -e ML_ACCESS_TOKEN=opcional_mercado_livre \
  --name arbilocal arbilocal
```

Depois acesse `http://SEU_IP:8765` ou o domínio que apontar para o servidor.

## Dashboard

```bash
python dashboard_server.py
```

Abra no navegador: `http://127.0.0.1:8765/`

## Docker

```bash
docker build -t arbilocal .
docker run -p 8765:8765 \
  -e ARBILOCAL_HOST=0.0.0.0 \
  -e BRAVE_API_KEY=sua_chave \
  -e ARBILOCAL_API_KEY=opcional_protecao \
  arbilocal
```

## Publicar no GitHub

1. Crie um repositório **vazio** em [github.com/new](https://github.com/new) (sem README se for usar este projeto como primeiro commit).

2. No PC, na pasta do projeto:

```bash
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

(Se o GitHub pedir autenticação, use **Personal Access Token** ou **GitHub CLI** `gh auth login`.)

## Licença

Defina a licença no repositório conforme sua necessidade.
