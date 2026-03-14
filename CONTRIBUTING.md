# Contributing

Obrigado pelo interesse em contribuir com o hypokrates! Este guia cobre tudo que você precisa saber.

## Como contribuir

### Reportar bugs

Abra uma [issue](https://github.com/brunoescalhao/hypokrates/issues) com:
- Versão do hypokrates e Python
- Código mínimo que reproduz o problema
- Output/traceback completo
- Comportamento esperado vs obtido

### Sugerir funcionalidades

Abra uma issue com a label `enhancement`. Descreva o caso de uso, não apenas a solução.

### Pull Requests

1. Fork o repositório
2. Crie uma branch: `git checkout -b feat/minha-feature`
3. Implemente com testes
4. Verifique que tudo passa (veja abaixo)
5. Abra o PR descrevendo o que mudou e por quê

## Setup de desenvolvimento

```bash
# Clone
git clone https://github.com/brunoescalhao/hypokrates.git
cd hypokrates

# Virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Instalar em modo dev
pip install -e ".[dev]"

# Pre-commit hooks
pre-commit install
pre-commit install --hook-type pre-push
```

## Verificação

Todos os checks devem passar antes de abrir PR:

```bash
# Testes
pytest tests/ -v --timeout=30

# Linting
ruff check hypokrates/ tests/
ruff format --check hypokrates/ tests/

# Type checking (strict)
mypy hypokrates/

# Coverage (gate: 85%)
pytest tests/ --cov=hypokrates --cov-fail-under=85
```

## Padrões de código

### Type hints

- mypy strict — zero `any`
- `unknown` + type guards quando o tipo é desconhecido
- Type-only imports: `from __future__ import annotations` + `TYPE_CHECKING`

### Nomenclatura

- Variáveis/funções: `snake_case`
- Classes/Types: `PascalCase`
- Constantes: `UPPER_SNAKE_CASE`
- API pública em inglês
- Domínio médico pode usar português nos comentários

### Docstrings

Google convention. Toda função pública precisa de docstring.

```python
def compute_prr(table: ContingencyTable) -> DisproportionalityResult:
    """PRR = (a/(a+b)) / (c/(c+d)), CI via Rothman-Greenland.

    Args:
        table: Tabela de contingência 2x2.

    Returns:
        DisproportionalityResult com PRR, CI 95% e flag de significância.
    """
```

### Imports

```python
from __future__ import annotations

# stdlib
import math
from typing import TYPE_CHECKING

# third-party
from pydantic import BaseModel

# local
from hypokrates.models import MetaInfo

if TYPE_CHECKING:
    from collections.abc import Sequence
```

### Tratamento de erros

- Nunca catch vazio ou com apenas `console.log`
- Logar com contexto: operação, IDs relevantes, mensagem do erro
- Mensagens para o usuário: genéricas. Mensagens no log: específicas

### Testes

- Todo módulo novo precisa de testes
- Golden data para respostas de API (fixtures JSON em `tests/golden_data/`)
- Mock HTTP via `respx` — nunca chamar APIs reais em testes unitários
- Testes de integração marcados com `@pytest.mark.integration`

## Estrutura do projeto

```
hypokrates/
├── config.py          # HypokratesConfig singleton
├── constants.py       # Source enum, URLs, settings
├── exceptions.py      # Hierarquia HypokratesError
├── models.py          # Drug, AdverseEvent, MetaInfo
├── sync.py            # Wrappers síncronos
├── cache/             # DuckDB cache thread-safe
├── http/              # Retry, rate limiter, client factory
├── faers/             # OpenFDA/FAERS (client, parser, models)
├── stats/             # PRR, ROR, IC — detecção de sinais
├── evidence/          # EvidenceBlock com proveniência
├── contracts/         # Protocol classes (interfaces)
└── utils/             # Helpers (validation, time, result)

tests/
├── golden_data/       # Fixtures JSON por fonte
├── test_faers/        # Testes FAERS
├── test_stats/        # Testes stats
├── test_evidence/     # Testes evidence
├── test_contracts/    # Testes contracts
└── ...
```

## Adicionando uma nova fonte de dados

1. Crie `hypokrates/{fonte}/` com `__init__.py`, `api.py`, `client.py`, `models.py`, `constants.py`, `parser.py`
2. Adicione a fonte ao `Source` enum em `constants.py`
3. Configure TTL em `cache/policies.py` e rate limit em `constants.py`
4. Adicione sync wrapper em `sync.py`
5. Exporte em `__init__.py`
6. Crie golden data em `tests/golden_data/{fonte}/`
7. Escreva testes espelhando a estrutura de `test_faers/`

## Commits

Formato em português:

```
tipo: descrição curta

Tipos: feat, fix, refactor, docs, style, test, chore, perf, security
```

Um concern por commit. Nunca misturar feature + refatoração.

## Segurança

- Nunca commitar `.env`, chaves de API ou segredos
- Rate limiting obrigatório para toda fonte
- Cache obrigatório — toda chamada HTTP passa pelo DuckDB

## Licença

Ao contribuir, você concorda que sua contribuição será licenciada sob a [MIT License](LICENSE).
