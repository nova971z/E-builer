# J.A.R.V.I.S. Trading System v3.0

A professional-grade crypto trading dashboard inspired by MEXC Futures Desktop. Built with Flask, TradingView Lightweight Charts, and pure Python technical analysis — no numpy/pandas dependencies.

## Features

### Market Data
- Real-time candlestick charts with 8 timeframes (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
- Live order book with depth visualization and buy/sell ratio
- Recent trades feed with color-coded buy/sell
- Multi-pair scrolling ticker (BTC, ETH, SOL, XRP, DOGE, GOLD, SILVER)
- 24h stats: price, change, high, low, volume, funding, open interest

### Technical Indicators (11)
- **Trend**: EMA 9/21/50/200, SMA, Bollinger Bands (20,2)
- **Momentum**: RSI (14, Wilder's), MACD (12,26,9), Stochastic RSI, Williams %R
- **Volatility**: ATR (14), Bollinger Band width
- **Volume**: OBV, Volume histogram
- All toggleable as chart overlays

### Intelligence Engine
- **Market Regime Detector**: BULL / BEAR / RANGE / CRISIS with confidence scoring
- **Signal Engine**: Multi-indicator weighted scoring (-300 to +300), regime-adjusted
- **Risk Engine**: 7 absolute veto conditions, 4-level drawdown tracking
- **Dip/Top Detector**: RSI divergence, volume climax, Wyckoff Spring, confluence scorer

### Trading
- Paper trading with virtual execution (50-trade gate before live)
- Order form: Limit/Market/Plan/Trailing, leverage 1-200x, TP/SL
- Micro-position engine: 5% capital max, 5 positions, $10 default
- Kill switch with immediate halt
- Exchange management (MEXC via CCXT)

### AI Assistant
- J.A.R.V.I.S. chat powered by Anthropic Claude (Iron Man persona, French)
- Voice commands via Web Speech API (19 commands)
- Quick action buttons: Analyse, Sentiment, Signal, Risque, Dip/Top

### Monitoring
- Drawdown tracking: 3 alert levels (yellow 5%, orange 10%, red 15%)
- Economic calendar with event mode (FOMC, CPI, NFP, ECB)
- News aggregation via RSS
- Trade journal and CSV export

## Quick Start

```bash
# Clone
git clone https://github.com/nova971z/E-builer.git
cd E-builer

# Install dependencies
pip install -r requirements.txt

# Start server
./scripts/start.sh

# Or start in background
./scripts/start.sh --bg

# Open dashboard
open http://localhost:5000
```

## Requirements

- Python 3.8+
- Flask, Flask-CORS, Requests, Cryptography
- Optional: CCXT (exchange trading), Anthropic (AI chat)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_PORT` | Server port | `5000` |
| `ANTHROPIC_API_KEY` | Claude API key for JARVIS AI | None (set via Settings) |

## Architecture

```
E-builer/
├── server.py            # Flask backend — 33 API routes, ~2800 lines
├── dashboard.html       # Frontend SPA — chart, order book, forms, ~3100 lines
├── lw-charts.js         # TradingView Lightweight Charts v4.2.1
├── requirements.txt     # Python dependencies
├── scripts/
│   ├── start.sh         # Start server (foreground/background)
│   ├── kill.sh          # Stop server
│   ├── health-check.sh  # Test all 22 API routes
│   ├── backup.sh        # Database backup with rotation
│   ├── export-trades.sh # Export trades to CSV
│   └── code-review.sh   # Automated code review (6 checks)
├── CLAUDE.md            # Claude Code conventions
└── .gitignore
```

## API Reference (33 routes)

### Market Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/candles` | OHLCV klines (symbol, interval, limit) |
| GET | `/api/price` | Current price + 24h stats |
| GET | `/api/orderbook` | Bid/ask depth (limit) |
| GET | `/api/trades` | Recent trades (30) |
| GET | `/api/ticker` | Multi-pair ticker |

### Indicators & Intelligence
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/indicators` | 11 indicators + regime + signal + risk |
| GET | `/api/dip-top` | Dip/top detectors + confluence score |
| GET | `/api/whales` | Large trade detection |

### Sentiment
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/funding` | Funding rate + percentile |
| GET | `/api/fear-greed` | Fear & Greed index |
| GET | `/api/sentiment` | OI + Long/Short ratio |

### News & Calendar
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/news` | RSS news aggregation |
| POST | `/api/news/summarize` | AI news summary |
| GET | `/api/calendar` | Economic calendar + event mode |

### AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/jarvis` | JARVIS AI chat |

### Trading
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/execute` | Execute order (paper/live) |
| GET | `/api/positions` | Open positions |
| GET | `/api/balance` | Account balance |
| POST | `/api/close` | Close position |
| GET | `/api/paper/status` | Paper trading stats |
| GET | `/api/paper/history` | Paper trade history |

### Exchange Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/exchanges/add` | Connect exchange |
| GET | `/api/exchanges/list` | List exchanges |
| DELETE | `/api/exchanges/remove` | Remove exchange |
| POST | `/api/exchanges/test` | Test connection |

### Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/drawdown` | Drawdown status |
| POST | `/api/killswitch` | Toggle kill switch |
| GET | `/api/killswitch/status` | Kill switch status |
| GET | `/api/journal` | Trade journal |
| GET | `/api/export/csv` | Export trades CSV |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | System health |
| GET | `/` | Dashboard |

## Paper Trading Workflow

1. System starts in **paper mode** with virtual 10,000 USDT
2. Execute trades via the order form — all orders go through paper engine
3. After **50 completed trades** with documented performance, live trading unlocks
4. Risk engine applies same veto rules in both modes
5. Export trade history anytime via CSV

## Voice Commands

Say these keywords to trigger actions (French locale):

| Command | Action |
|---------|--------|
| bitcoin, btc | Switch to BTC/USDT |
| ethereum, eth | Switch to ETH/USDT |
| solana, sol | Switch to SOL/USDT |
| ripple, xrp | Switch to XRP/USDT |
| doge, dogecoin | Switch to DOGE/USDT |
| gold, or | Switch to GOLD |
| silver, argent | Switch to SILVER |
| kill, stop | Toggle kill switch |
| analyse | Full analysis of current pair |
| signal | Current trading signal |
| risque | Portfolio risk assessment |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| J | Toggle JARVIS chat |
| K | Toggle kill switch |
| 1-8 | Switch timeframe (1m to 1w) |
| Escape | Close modals/chat |

## Scripts

```bash
# Start server
./scripts/start.sh              # Foreground
./scripts/start.sh --bg         # Background
./scripts/start.sh --port 8080  # Custom port

# Stop server
./scripts/kill.sh
./scripts/kill.sh --port 8080

# Health check (22 routes)
./scripts/health-check.sh
./scripts/health-check.sh --verbose

# Database backup
./scripts/backup.sh             # Default: keep 10
./scripts/backup.sh --keep 20

# Export trades
./scripts/export-trades.sh
./scripts/export-trades.sh --output ~/exports

# Code review
./scripts/code-review.sh
```

## Tech Stack

- **Backend**: Python 3 / Flask / SQLite (WAL mode)
- **Frontend**: Vanilla JS / TradingView Lightweight Charts v4.2.1
- **Data**: Binance API (market data), Stooq (gold/silver fallback)
- **AI**: Anthropic Claude API (optional)
- **Exchange**: CCXT / MEXC (optional)
- **Security**: Fernet encryption for API keys, parameterized SQL

## License

Private — All rights reserved.
