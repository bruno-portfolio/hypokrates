# Async & Sync

hypokrates is async-first — all public API functions are `async`. Sync wrappers are provided for convenience.

## When to Use What

| Environment | Approach | Import |
|-------------|----------|--------|
| Script | `asyncio.run()` | `from hypokrates.faers import api as faers` |
| Jupyter Notebook | Top-level `await` or sync | Either |
| FastAPI / Starlette | Native `await` | `from hypokrates.faers import api as faers` |
| Flask / Django | Sync wrappers | `from hypokrates.sync import faers` |
| Quick prototyping | Sync wrappers | `from hypokrates.sync import faers` |

---

## Async Usage

### Script

```python
import asyncio
from hypokrates.faers import api as faers

async def main():
    result = await faers.top_events("propofol")
    for event in result.events:
        print(f"{event.term}: {event.count}")

asyncio.run(main())
```

### Jupyter Notebook

Jupyter has a running event loop, so you can `await` directly in cells:

```python
from hypokrates.faers import api as faers

result = await faers.top_events("propofol")  # top-level await works in Jupyter
```

### FastAPI

```python
from fastapi import FastAPI
from hypokrates.cross import api as cross

app = FastAPI()

@app.get("/hypothesis/{drug}/{event}")
async def get_hypothesis(drug: str, event: str):
    result = await cross.hypothesis(drug, event)
    return {
        "classification": result.classification,
        "summary": result.summary,
    }
```

### Parallel Queries with `asyncio.gather()`

Run independent queries concurrently:

```python
import asyncio
from hypokrates.faers import api as faers

async def main():
    propofol, midazolam, ketamine = await asyncio.gather(
        faers.top_events("propofol"),
        faers.top_events("midazolam"),
        faers.top_events("ketamine"),
    )
    print(f"Propofol: {len(propofol.events)} events")
    print(f"Midazolam: {len(midazolam.events)} events")
    print(f"Ketamine: {len(ketamine.events)} events")

asyncio.run(main())
```

!!! tip "The `hypothesis()` function already uses `asyncio.gather()` internally"
    FAERS signal detection and PubMed search run in parallel — no need to wrap it yourself.

---

## Sync Usage

The `hypokrates.sync` module provides sync wrappers for all public functions:

```python
from hypokrates.sync import faers, stats, pubmed, cross

# All calls are synchronous — no await needed
result = faers.top_events("propofol")
signal = stats.signal("propofol", "bradycardia")
papers = pubmed.count_papers("propofol", "bradycardia")
hyp = cross.hypothesis("propofol", "bradycardia")
```

### Available Sync Wrappers

| Module | Functions |
|--------|-----------|
| `faers` | `adverse_events()`, `top_events()`, `compare()` |
| `stats` | `signal()` |
| `pubmed` | `count_papers()`, `search_papers()` |
| `cross` | `hypothesis()` |

### How Sync Wrappers Work

Sync wrappers detect whether an event loop is already running:

- **No event loop** (scripts, CLI): Uses `asyncio.run()`
- **Event loop running** (Jupyter, some frameworks): Runs in a separate thread via `ThreadPoolExecutor`

This means sync wrappers work everywhere, but async is preferred for performance in concurrent contexts.
