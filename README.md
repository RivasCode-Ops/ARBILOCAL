# ARBILOCAL

Análise de revenda (Mercado Livre + custo + regras), CLI `main.py`, dashboard local `dashboard_server.py` e busca opcional de fornecedores na web (Brave / Google CSE).

## Requisitos

- Python 3.10+ recomendado
- Dependências: `pip install -r requirements.txt`

## Configuração rápida

1. Copie `data/aliexpress_costs.example.json` para `data/aliexpress_costs.json` e edite os custos, **ou** use `--custo` / variável `ALIEXPRESS_COST_BRL`.
2. Mercado Livre: se receber 403, defina `ML_ACCESS_TOKEN` no ambiente.
3. Busca web no painel (opcional): `BRAVE_API_KEY` **ou** `GOOGLE_API_KEY` + `GOOGLE_CSE_ID`.

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

## Licença

Defina a licença no repositório conforme sua necessidade.
