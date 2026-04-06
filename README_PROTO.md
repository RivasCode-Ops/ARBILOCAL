# ARBILOCAL: modo `proto` vs modo `run`

## 1. O que é o modo proto

O comando `python main.py proto` executa o motor **`core.engine_proto.gerar_resultado(...)`** com dados que você informa na linha de comando (ou valores padrão fixos). É um **teste isolado**: não consulta rede, não usa banco de dados e não lê nem grava arquivos como parte do fluxo do proto.

## 2. O que é o modo run

O comando `python main.py run ...` é o **fluxo real do ARBILOCAL**: resolve custo (configuração/env/JSON), obtém evidência de mercado (API do Mercado Livre e/ou JSON de busca), calcula números com taxa ML configurável e aplica as **regras do sistema principal** (`core.rules.decide`, parâmetros `ARBILOCAL_*`, etc.).

## 3. Diferenças principais

| Aspecto | `proto` | `run` |
|--------|---------|--------|
| Entrada | Termo, custo e lista de preços (manual ou padrão) | Termo de busca + custo + opcionalmente `--ml-json`, `--precos` no formato do `run`, etc. |
| Rede / dados | Nenhuma | Mercado Livre via HTTP (ou arquivo JSON da busca) |
| Margem (proto) | **Sobre o custo**: \((\text{lucro} / \text{custo}) \times 100\) | **Sobre o preço de venda de referência** (média da amostra ML), no `compute_analysis` |
| Concorrência (proto) | **Simplificada**: derivada só da **quantidade de preços** na lista informada | Baseada em **total de resultados** da busca MLB e regras do `decide` |
| Decisão | Regras fixas do `engine_proto` (APROVAR / TESTAR / DESCARTAR) | Recomendações e veredito do sistema principal |

**Importante:** os vereditos e números do **proto** e do **run** **não** são equivalentes; não devem ser comparados como se fossem o mesmo critério.

## 4. Quando usar cada um

- **Use `proto`** para validar rapidamente a lógica do protótipo, ensaiar listas de preços e custos sem depender de API ou arquivos de mercado.
- **Use `run`** quando quiser a **análise real** do ARBILOCAL com dados de mercado e regras oficiais do projeto.

## 5. Fluxo prático de uso

Encadeamento atual dos subcomandos que orbitam o motor proto (sem rede, sem banco):

- **salvar** → alimentar a fila de produtos de interesse (`proto-salvar` grava termo e custo em `data/produtos_salvos.json`).
- **listar** → ver os produtos salvos e seus índices (`proto-listar`).
- **analisar-salvo** → aplicar preços reais ao custo salvo (`proto-analisar-salvo` usa o índice da listagem e `--precos`; roda `gerar_resultado` e grava JSON em `reports/` como o `proto`).
- **comparar** → ver a diferença em relação à última execução (mensagem automática **Comparação com última execução** após cada análise que salva em `reports/`).
- **histórico** → ver visão agregada das execuções (`proto-historico` sobre os `proto_*.json` em `reports/`).
- **decidir** → usar o veredito final do motor (linhas **Decisão** e **Motivos** na saída do proto / proto-analisar-salvo).

Exemplo mínimo, nesta ordem:

```bash
python main.py proto-salvar --termo "fone bluetooth" --custo 55
python main.py proto-listar
python main.py proto-analisar-salvo --indice 1 --precos "99.9,109.9,119.9"
python main.py proto-historico
```

## 6. Exemplos de execução

Proto com padrões de demonstração:

```bash
python main.py proto
```

Proto com entrada manual:

```bash
python main.py proto --termo "fone bluetooth" --custo 55 --precos "99.9,109.9,119.9,89.9"
```

Fluxo real (exemplo; exige custo resolvido e acesso ou JSON do ML conforme seu ambiente):

```bash
python main.py run "fone bluetooth" --custo 55
```

Consulte `python main.py run -h` para todas as opções do modo `run`.
