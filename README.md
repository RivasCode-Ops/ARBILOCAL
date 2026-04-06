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

## Dashboard

```bash
python dashboard_server.py
```

Abra no navegador: `http://127.0.0.1:8765/`

## Docker

```bash
docker build -t arbilocal .
docker run -p 8765:8765 -e ML_ACCESS_TOKEN=... arbilocal
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
