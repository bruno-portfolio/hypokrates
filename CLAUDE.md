# hypokrates — Regras para o Claude Code

## Stack
Python 3.11+, Hatchling, httpx, DuckDB, Pydantic 2, scipy, mypy strict, ruff. curl_cffi (opcional, para ClinicalTrials.gov).

## Comandos
- `pip install -e ".[dev]"` — instalar dev
- `pytest tests/` — rodar testes
- `ruff check hypokrates/` — linting
- `ruff format hypokrates/` — formatacao
- `mypy hypokrates/` — type checking

## Regras

- **mypy strict**: zero `any`. Usar `unknown` + type guards.
- **Async-first**: funcoes publicas sao async. Sync wrapper em `hypokrates/sync.py`.
- **Cache obrigatorio**: toda chamada HTTP passa pelo DuckDB cache.
- **Rate limiting**: respeitar limites por fonte (FAERS: 240/min com key, 40/min sem; PubMed: 600/min com key, 180/min sem; RxNorm: 120/min; DailyMed: 60/min; ClinicalTrials.gov: 50/min; OpenTargets: 30/min). MeSH compartilha rate com PubMed (mesmo E-utilities).
- **Testes**: todo modulo novo precisa de testes. Golden data para respostas de API.
- **Seguranca**: nunca commitar .env ou chaves. UA fixo `hypokrates/{version}`.

## Nomenclatura
- Variaveis/funcoes: `snake_case`
- Classes/Types: `PascalCase`
- Constantes: `UPPER_SNAKE_CASE`
- API publica em ingles. Commits em portugues.

## Arquivos importantes
- `hypokrates/config.py` — HypokratesConfig singleton
- `hypokrates/cache/duckdb_store.py` — Cache thread-safe
- `hypokrates/http/retry.py` — Retry com backoff
- `hypokrates/faers/api.py` — API publica FAERS
- `hypokrates/faers/client.py` — HTTP client OpenFDA
- `hypokrates/scan/api.py` — Scan automatico de eventos adversos
- `hypokrates/vocab/api.py` — Normalizacao de drogas (RxNorm) e MeSH
- `hypokrates/vocab/rxnorm_client.py` — HTTP client RxNorm
- `hypokrates/vocab/mesh_client.py` — HTTP client MeSH/NCBI
- `hypokrates/dailymed/api.py` — Bulas FDA (label_events, check_label)
- `hypokrates/dailymed/client.py` — HTTP client DailyMed
- `hypokrates/trials/api.py` — Trials clinicos (search_trials)
- `hypokrates/trials/client.py` — HTTP client ClinicalTrials.gov (curl_cffi + httpx fallback)
- `hypokrates/drugbank/api.py` — DrugBank (drug_info, drug_interactions, drug_mechanism)
- `hypokrates/drugbank/store.py` — DuckDB store para DrugBank XML
- `hypokrates/drugbank/parser.py` — Parser streaming XML via iterparse
- `hypokrates/opentargets/api.py` — OpenTargets (drug_adverse_events, drug_safety_score)
- `hypokrates/opentargets/client.py` — Client GraphQL OpenTargets
- `hypokrates/vocab/meddra.py` — Agrupamento MedDRA de termos sinonimos
- `hypokrates/anvisa/api.py` — ANVISA (buscar_medicamento, buscar_por_substancia, mapear_nome)
- `hypokrates/anvisa/store.py` — DuckDB store para ANVISA CSV (auto-download)
- `hypokrates/anvisa/constants.py` — Mapeamento PT↔EN (~95 drogas)

## Git
- Commits em portugues: `tipo: descricao`
- Tipos: feat, fix, refactor, docs, style, test, chore, perf
- Nao commitar automaticamente. Fornecer comandos para o usuario.
