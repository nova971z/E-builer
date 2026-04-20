# CLAUDE.md — Claude Code Project Conventions

## Project Overview

J.A.R.V.I.S. Trading System v3.0 — crypto trading dashboard with Flask backend and vanilla JS frontend.

## Architecture

- `server.py` — Single-file Flask backend (~2800 lines). All API routes, indicators, intelligence engine, trading logic.
- `dashboard.html` — Single-file frontend SPA (~3100 lines). Inline CSS + JS, TradingView Lightweight Charts.
- `lw-charts.js` — TradingView Lightweight Charts v4.2.1 (vendored, do not modify).

## Key Conventions

### Python (server.py)

- **No numpy/pandas** — All indicator calculations are pure Python. This is intentional to minimize dependencies.
- **Thread-safe Cache** — The `Cache` class uses `threading.Lock()`. Always use it for shared state.
- **SQLite WAL mode** — Database uses WAL for concurrent read/write. Never change journal mode.
- **Fernet encryption** — API keys are encrypted at rest via `cryptography.fernet`. Key stored in `secret.key`.
- **Binance API proxy** — All market data routes proxy through `fetch_binance()` which handles caching and errors.
- **Gold/Silver via Stooq** — `fetch_yfinance_gold_silver()` uses Stooq CSV endpoint as fallback.

### Frontend (dashboard.html)

- **Vanilla JS only** — No frameworks, no build step. Everything is inline in the HTML file.
- **Function style** — Use `function` declarations, not arrow functions (browser compat).
- **`$()` helper** — Shorthand for `document.getElementById()`. Used everywhere.
- **`fmt()` / `fmtK()`** — Number formatting helpers. Use these for all displayed values.
- **`epochToLocal()`** — Converts Unix timestamps for chart display. Always use for chart time data.

### CSS

- All CSS is in a single `<style>` block using CSS custom properties (`:root` variables).
- Color scheme: `--bg` (dark), `--surface` (panels), `--green` (bullish), `--red` (bearish), `--accent` (JARVIS blue), `--yellow` (active/highlight).

## Important Classes

| Class | Purpose |
|-------|---------|
| `Cache` | Thread-safe TTL cache for API responses |
| `MarketRegimeDetector` | Detects BULL/BEAR/RANGE/CRISIS market states |
| `SignalEngine` | Multi-indicator weighted signal generation |
| `RiskEngine` | Risk assessment with 7 veto conditions |
| `DipTopDetector` | RSI divergence, volume climax, Wyckoff patterns |
| `ExchangeAdapter` | Abstract base for exchange integrations |
| `MEXCAdapter` | MEXC exchange via CCXT |
| `MicroPositionEngine` | Position sizing and risk limits |
| `PaperTrader` | Virtual trade execution engine |

## API Route Pattern

All routes follow this pattern:
- Path: `/api/<resource>`
- Methods: GET for reads, POST for writes, DELETE for removes
- Response: JSON with data fields or `{"error": "message"}`
- Errors from external APIs return 502 with descriptive message

## Roadmap & Navigation

- **`PLAN.md`** — Roadmap complète des 10 étapes d'amélioration avec :
  - Carte de navigation (numéros de ligne exacts de server.py et dashboard.html)
  - 10 étapes détaillées avec sous-tâches numérotées et critères de validation
  - Matrice de dépendances et ordre d'exécution optimal
  - Tableau de suivi d'avancement (cocher après chaque étape)
  - Checklist post-implémentation et protocoles de test
  - Notes de reprise inter-session
- **Toujours lire PLAN.md avant de commencer une étape**
- **Toujours mettre à jour PLAN.md après chaque étape**

## Testing

```bash
# Syntax check
python3 -m py_compile server.py

# Health check (server must be running)
./scripts/health-check.sh

# Automated code review
./scripts/code-review.sh
```

## Common Tasks

### Adding a new indicator
1. Add `calc_<name>(data, ...)` function after the existing indicator functions
2. Call it from `compute_all_indicators()` and add to the returned dict
3. Frontend: add toggle button in `.chart-toolbar`, handle in `toggleIndicator()`

### Adding a new API route
1. Add Flask route in server.py in the appropriate section
2. Follow existing error handling pattern (try/except, return JSON)
3. Add to health-check.sh route list

### Starting a new enhancement step
1. Read PLAN.md — find the next unchecked step in Section 4.1
2. Read the step's detail section (search "### ÉTAPE X.0")
3. Use text anchors (Section 6.2) to find insertion points — don't trust line numbers blindly
4. Follow the sub-tasks in order
5. Run the post-implementation checklist (Section 5.1)
6. Update PLAN.md: check sub-tasks, update navigation map, mark step as done
7. Commit with message: `feat: step XX — <description>`

### Adding a new exchange
1. Create `class NewAdapter(ExchangeAdapter)` implementing all abstract methods
2. Register in `ExchangeManager` constructor
3. Add option in dashboard.html `#ex-type` select

## Do Not

- Do not add numpy, pandas, or heavy data science libraries
- Do not split server.py into multiple files (single-file architecture is intentional)
- Do not split dashboard.html into multiple files
- Do not modify lw-charts.js (vendored dependency)
- Do not commit jarvis.db, secret.key, or .env files
- Do not use arrow functions in dashboard.html JS
- Do not remove the 50-trade paper gate — it is a safety feature
- Do not start coding an enhancement step without reading PLAN.md first
- Do not skip the post-implementation checklist after completing a step
- Do not trust PLAN.md line numbers after multiple steps — use text anchors
