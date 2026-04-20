## 1. CARTE DE NAVIGATION — COORDONNÉES EXACTES

> **Usage** — Avant chaque étape, consulter cette carte pour localiser
> précisément les zones d'insertion. Après chaque étape, mettre à jour
> les numéros de ligne qui ont bougé (décalage = lignes ajoutées avant la zone).

---

### 1.1 POINTS D'INSERTION CRITIQUES (ancres principales)

| Ancre | Fichier | Ligne | Repère textuel |
|-------|---------|-------|----------------|
| FIN CSS | `dashboard.html` | `L:1175` | `</style>` |
| DEBUT BODY | `dashboard.html` | `L:1177` | `<body>` |
| FIN BODY HTML | `dashboard.html` | `L:1580` | `<!-- Lightweight Charts -->` |
| DEBUT JS | `dashboard.html` | `L:1582` | `<script>` |
| FIN GLOBAL STATE | `dashboard.html` | `L:1614` | fin du bloc `indicatorState` |
| FIN UTILITIES | `dashboard.html` | `L:1635` | fin de `epochToLocal()` |
| AVANT INIT | `dashboard.html` | `L:3142` | `// ========== INIT ON DOM READY ==========` |
| FIN INIT | `dashboard.html` | `L:3173` | `</script>` |
| AVANT ROUTE "/" | `server.py` | `L:2785` | `@app.route("/")` |
| AVANT MAIN | `server.py` | `L:2799` | `if __name__ == "__main__":` |
| FIN FICHIER | `server.py` | `L:2803` | `app.run(...)` |

---

### 1.2 dashboard.html — CSS (L:8 → L:1175)

| Zone CSS | Lignes | Sélecteurs clés |
|----------|--------|-----------------|
| **Variables :root** | `L:9 → L:40` | `--bg`, `--surface`, `--green`, `--red`, `--accent`, `--yellow` |
| **Reset & Base** | `L:41 → L:62` | `*`, `body`, `html`, scrollbar |
| **Navbar** | `L:64 → L:161` | `.navbar`, `.navbar-logo`, `.btn-nav`, `.btn-kill`, `.navbar-clock` |
| **Asset Bar** | `L:163 → L:227` | `.asset-bar`, `.asset-selector`, `.asset-price`, `.asset-stat`, `.asset-shortcuts` |
| **Main Layout** | `L:229 → L:234` | `.main-layout` (CSS grid 3 colonnes) |
| **Chart Area** | `L:235 → L:354` | `.chart-area`, `.chart-tabs`, `.chart-toolbar`, `.toolbar-toggle`, `.chart-main-wrap`, `.chart-ohlcv-overlay`, `.subchart-wrap`, `.subchart-label` |
| **Drawing Toolbar** | `L:356 → L:379` | `.draw-toolbar`, `.draw-toolbar button` |
| **Right Panel** | `L:381 → L:389` | `.right-panel` |
| **Order Book** | `L:391 → L:509` | `.orderbook`, `.ob-rows`, `.ob-row`, `.ob-spread`, `.ob-ratio-bar` |
| **Order Form** | `L:511 → L:673` | `.order-form`, `.of-tabs`, `.of-margin-mode`, `.of-leverage`, `.of-type-tabs`, `.of-field`, `.of-pct-btns`, `.of-tpsl`, `.of-info`, `.of-actions`, `.btn-long`, `.btn-short` |
| **Wallet** | `L:675 → L:707` | `.wallet-section`, `.wallet-row`, `.wallet-actions` |
| **Bottom Panel** | `L:709 → L:806` | `.bottom-panel`, `.bp-tabs`, `.bp-table-wrap`, `.bp-table`, `.bp-empty` |
| **Recent Trades** | `L:808 → L:827` | `.trades-list`, `.t-row`, `.t-price`, `.t-qty`, `.t-time` |
| **JARVIS Chat** | `L:829 → L:949` | `.jarvis-chat`, `.jc-header`, `.jc-messages`, `.jc-msg`, `.jc-quick-btns`, `.jc-input-wrap`, `.btn-mic` |
| **Alert Banners** | `L:951 → L:993` | `.alert-banner`, `.alert-kill`, `.alert-event`, `.alert-drawdown`, `.alert-diptop`, `@keyframes slide-down` |
| **Footer** | `L:994 → L:1067` | `.footer`, `.ft-status`, `.ft-dot`, `.ft-ticker`, `.ft-ticker-inner`, `.ft-ticker-item`, `.ft-info`, `.ft-regime`, `.ft-mode`, `@keyframes ticker-scroll` |
| **Modals** | `L:1069 → L:1147` | `.modal-overlay`, `.modal`, `.modal-header`, `.modal-body`, `.modal-field`, `.modal-footer` |
| **Exchange List** | `L:1149 → L:1174` | `.exchange-list`, `.exchange-item` |
| **>>> INSÉRER ICI** | `L:1174` | **Nouvelle CSS → avant L:1175 (`</style>`)** |

---

### 1.3 dashboard.html — HTML BODY (L:1177 → L:1579)

| Zone HTML | Lignes | IDs / Classes clés |
|-----------|--------|---------------------|
| **Navbar** | `L:1179 → L:1198` | `#btn-killswitch`, `#clock` |
| **Alert Banners** | `L:1200 → L:1216` | `#alert-kill`, `#alert-event`, `#alert-drawdown`, `#alert-diptop` |
| **Asset Bar** | `L:1218 → L:1244` | `#sym-select`, `#asset-price`, `#stat-change`, `#stat-high`, `#stat-low`, `#stat-vol`, `#stat-funding`, `#stat-oi` |
| **Main Layout (ouverture)** | `L:1246 → L:1248` | `div.main-layout` |
| **Drawing Toolbar** | `L:1249 → L:1260` | `div.draw-toolbar` (boutons dessin) |
| **Chart Area** | `L:1261 → L:1330` | `#chart-container`, `#ohlcv-overlay`, `#rsi-container`, `#macd-container` |
| **Chart Tabs** | `L:1264 → L:1271` | Boutons Chart / Info / Depth |
| **Chart Toolbar** | `L:1273 → L:1290` | Timeframes (1m→1w) + Indicateurs (BB, EMA, VOL) |
| **Main Chart** | `L:1292 → L:1303` | `#chart-container`, `#ov-o/h/l/c/v` |
| **RSI Sub-chart** | `L:1304 → L:1309` | `#rsi-container` |
| **MACD Sub-chart** | `L:1310 → L:1315` | `#macd-container` |
| **Bottom Panel** | `L:1316 → L:1330` | `#pos-count`, `#bp-content` (tabs: Positions, Open Orders, History, Journal) |
| **Right Panel (ouverture)** | `L:1332 → L:1333` | `div.right-panel` |
| **Order Book** | `L:1334 → L:1365` | `#ob-asks`, `#ob-bids`, `#ob-spread`, `#spread-pct`, `#ratio-buy`, `#ratio-sell` |
| **Order Form** | `L:1367 → L:1422` | `#order-price`, `#order-qty`, `#order-tp`, `#order-sl`, `#lev-display`, `#qty-unit` |
| **Wallet** | `L:1424 → L:1435` | `#w-balance`, `#w-equity`, `#w-available`, `#w-pnl` |
| **Recent Trades** | `L:1436 → L:1447` | `#trades-list` |
| **Fin Main Layout** | `L:1448` | `</div><!-- /main-layout -->` |
| **JARVIS Chat** | `L:1450 → L:1472` | `#jarvis-chat`, `#jc-messages`, `#jc-input`, `#btn-mic` |
| **Settings Modal** | `L:1474 → L:1507` | `#modal-settings`, `#set-api-key`, `#set-default-symbol`, `#set-capital` |
| **Exchange Modal** | `L:1509 → L:1542` | `#modal-exchange`, `#ex-type`, `#ex-name`, `#ex-key`, `#ex-secret` |
| **Kill Switch Modal** | `L:1544 → L:1560` | `#modal-kill` |
| **Footer** | `L:1562 → L:1578` | `#ft-dot`, `#ft-net`, `#ft-ticker`, `#ft-regime`, `#ft-signal`, `#ft-fg`, `#ft-dd`, `#ft-mode` |
| **>>> INSÉRER HTML** | `L:1579` | **Nouveau HTML → avant L:1580 (`<!-- Lightweight Charts -->`)** |

---

### 1.4 dashboard.html — JAVASCRIPT (L:1582 → L:3173)

| Zone JS | Lignes | Fonctions |
|---------|--------|-----------|
| **Global State** | `L:1585 → L:1614` | `API`, `currentSymbol`, `currentInterval`, `candleData`, chart/series refs, `indicatorState` |
| **Utilities** | `L:1616 → L:1635` | `fmt()`, `fmtK()`, `$()`, `epochToLocal()` |
| **Chart Theme** | `L:1637 → L:1671` | `chartOptions` (objet de config TradingView) |
| **Init Main Chart** | `L:1672 → L:1720` | `initMainChart()` |
| **Init Sub-Charts** | `L:1722 → L:1793` | `subChartOptions`, `initRSIChart()`, `initMACDChart()` |
| **Sync Time Scales** | `L:1795 → L:1828` | `syncTimeScales()` |
| **Load Candles** | `L:1830 → L:1874` | `loadCandles(symbol, interval)` |
| **Load Indicators** | `L:1876 → L:1940` | `loadIndicators(symbol, interval)` |
| **Indicator Overlay Helpers** | `L:1942 → L:1998` | `buildOverlayData()`, `applyBollinger()`, `removeBollinger()`, `applyEMA()`, `removeEMA()` |
| **Toggle Indicators** | `L:2000 → L:2017` | `toggleIndicator(key)` |
| **Change Symbol/TF** | `L:2019 → L:2050` | `changeSymbol(sym)`, `changeTF(tf)` |
| **Display Helpers** | `L:2052 → L:2076` | `updateAssetPrice()`, `updateRegimeDisplay()`, `updateSignalDisplay()` |
| **Clock** | `L:2077 → L:2082` | `updateClock()` |
| **Order Book** | `L:2083 → L:2171` | `obLastPrice`, `obLastDirection`, `loadOrderBook(symbol)` |
| **Recent Trades** | `L:2173 → L:2199` | `loadTrades(symbol)` |
| **Ticker** | `L:2201 → L:2245` | `loadTicker()` |
| **Price Data** | `L:2247 → L:2271` | `loadPriceData(symbol)` |
| **Funding + Sentiment** | `L:2273 → L:2306` | `loadFunding(symbol)`, `loadSentiment(symbol)` |
| **Fear & Greed** | `L:2308 → L:2324` | `loadFearGreed()` |
| **Drawdown** | `L:2326 → L:2349` | `loadDrawdown()` |
| **Kill Switch Status** | `L:2351 → L:2370` | `loadKillSwitchStatus()` |
| **Bottom Panel Tabs** | `L:2372 → L:2380` | `switchBPTab(tab)` |
| **Positions Table** | `L:2382 → L:2433` | `loadPositions()` |
| **Paper Trade History** | `L:2435 → L:2475` | `loadPaperHistory()` |
| **Order Form State** | `L:2477 → L:2482` | `orderTab`, `marginMode`, `orderType`, `leverage` |
| **Leverage Slider** | `L:2483 → L:2489` | `updateLeverage(val)` |
| **Order Tab/Type Switch** | `L:2490 → L:2527` | `switchOrderTab()`, `switchOrderType()` |
| **Margin Mode** | `L:2528 → L:2528` | (toggle isolated/cross) |
| **Field Adjustments** | `L:2529 → L:2569` | `adjustField()`, `getTickSize()`, `getQtyStep()`, `getPriceDecimals()`, `getQtyDecimals()` |
| **Qty Percentage** | `L:2571 → L:2582` | `setQtyPct(pct)` |
| **Order Info** | `L:2584 → L:2602` | `updateOrderInfo()` |
| **Execute Order** | `L:2604 → L:2661` | `executeOrder(side)` |
| **Close Position** | `L:2663 → L:2686` | `closePosition(posId)` |
| **Toast Notifications** | `L:2688 → L:2698` | `showToast(msg, type)` — inline CSS, pas de classe |
| **Paper Status** | `L:2700 → L:2720` | `loadPaperStatus()` |
| **Wallet / Balance** | `L:2722 → L:2741` | `loadWallet()` |
| **Kill Switch** | `L:2743 → L:2780` | `toggleKillSwitch()`, `confirmKillSwitch()`, `confirmKillSwitchOff()` |
| **Modals** | `L:2782 → L:2786` | `openModal()`, `closeModal()`, `showSettings()`, `showAddExchange()` |
| **Settings** | `L:2788 → L:2801` | `saveSettings()` |
| **Exchange Mgmt** | `L:2803 → L:2874` | `loadExchangeList()`, `addExchange()`, `removeExchange()` |
| **JARVIS Chat** | `L:2876 → L:2923` | `toggleJarvisChat()`, `sendJarvisQuick()`, `sendJarvis()`, `appendChatMsg()` |
| **Voice Recognition** | `L:2925 → L:3006` | `recognition`, `isRecording`, `voiceCommands`, `toggleVoice()`, `stopVoice()` |
| **News** | `L:3008 → L:3018` | `loadNews()` |
| **Calendar** | `L:3020 → L:3035` | `loadCalendar()` |
| **Dip/Top Alerts** | `L:3037 → L:3062` | `loadDipTop(symbol)` |
| **Whale Tracking** | `L:3064 → L:3075` | `loadWhales(symbol)` |
| **Auto-Refresh** | `L:3076 → L:3118` | `refreshTimers`, `startAutoRefresh()` |
| **Keyboard Shortcuts** | `L:3120 → L:3140` | `keydown` listener (1-8 timeframes, Escape) |
| **Init on DOM Ready** | `L:3142 → L:3172` | `DOMContentLoaded` → init charts + load all data + start refresh |
| **>>> INSÉRER JS** | `L:3141` | **Nouveau JS → avant L:3142 (`// ========== INIT ON DOM READY ==========`)** |

---

### 1.5 server.py — STRUCTURE COMPLÈTE (L:1 → L:2803)

| Zone | Lignes | Contenu |
|------|--------|---------|
| **Docstring + Imports** | `L:1 → L:43` | shebang, docstring, 20 imports stdlib + 5 externals |
| **Configuration** | `L:45 → L:107` | `BASE_DIR`, `DB_PATH`, `APP_VERSION`, `SYMBOLS` dict (7 paires), `INTERVALS` list (16 TF), Flask app init, CORS, logging |
| **Cache** | `L:109 → L:131` | `class Cache` — TTL cache thread-safe, `get()`, `set()`, `invalidate()` |
| **Database** | `L:133 → L:202` | `get_db()`, `init_db()` — 5 tables: exchanges, paper_trades, trade_journal, settings, killswitch |
| **Encryption** | `L:204 → L:240` | `get_fernet()`, `encrypt_string()`, `decrypt_string()` — Fernet AES |
| **Settings** | `L:242 → L:261` | `get_setting()`, `set_setting()` |
| **Binance Proxy** | `L:263 → L:296` | `fetch_binance()` (GET avec cache TTL), `transform_klines()` |
| **Gold/Silver (Stooq)** | `L:298 → L:358` | `fetch_stooq_price()`, `generate_gold_silver_candles()` |
| **Indicateurs Part 1** | `L:360 → L:476` | `calc_sma()`, `calc_ema()`, `calc_rsi()`, `calc_macd()`, `_std_dev()`, `calc_bollinger()` |
| **Indicateurs Part 2** | `L:478 → L:616` | `calc_atr()`, `calc_stoch_rsi()`, `calc_adx()`, `calc_obv()`, `calc_williams_r()` |
| **compute_all_indicators** | `L:618 → L:690` | Batch computation des 11 indicateurs |
| **MarketRegimeDetector** | `L:692 → L:825` | `class MarketRegimeDetector` — BULL/BEAR/RANGE/CRISIS |
| **SignalEngine** | `L:826 → L:1047` | `class SignalEngine` — scoring multi-indicateurs pondéré |
| **RiskEngine** | `L:1049 → L:1202` | `class RiskEngine` — 7 veto conditions + drawdown tracking |
| **DipTopDetector** | `L:1204 → L:1406` | `class DipTopDetector` — RSI div, volume climax, Wyckoff, confluence |
| **ExchangeAdapter** | `L:1408 → L:1440` | `class ExchangeAdapter(ABC)` — 5 méthodes abstraites |
| **MEXCAdapter** | `L:1442 → L:1562` | `class MEXCAdapter` — CCXT impl |
| **GMXAdapter** | `L:1564 → L:1595` | `class GMXAdapter` — placeholder |
| **ExchangeManager** | `L:1597 → L:1687` | `class ExchangeManager` — multi-exchange registry |
| **MicroPositionEngine** | `L:1689 → L:1739` | `class MicroPositionEngine` — sizing 5% max, 5 concurrent |
| **PaperTrader** | `L:1741 → L:1828` | `class PaperTrader` — virtual execution, 50-trade gate |
| **Instances globales** | `L:1828` | `exchange_manager`, `position_engine`, `paper_trader` (après PaperTrader) |

---

### 1.6 server.py — ROUTES API (L:1830 → L:2793)

| Groupe | Lignes | Routes |
|--------|--------|--------|
| **Market Data** | `L:1830 → L:1987` | `GET /api/candles` L:1834, `GET /api/price` L:1857, `GET /api/orderbook` L:1888, `GET /api/trades` L:1926, `GET /api/ticker` L:1953 |
| **Intelligence** | `L:1989 → L:2131` | `GET /api/indicators` L:1993, `GET /api/dip-top` L:2032, `GET /api/whales` L:2058 |
| **Sentiment & News** | `L:2133 → L:2403` | `GET /api/funding` L:2137, `GET /api/fear-greed` L:2185, `GET /api/sentiment` L:2234, `GET /api/news` L:2267, `POST /api/news/summarize` L:2331, `GET /api/calendar` L:2369 |
| **AI Assistant** | `L:2405 → L:2475` | `POST /api/jarvis` L:2422 |
| **Execution** | `L:2477 → L:2624` | `POST /api/execute` L:2481, `GET /api/positions` L:2559, `GET /api/balance` L:2572, `POST /api/close` L:2587, `GET /api/paper/status` L:2615, `GET /api/paper/history` L:2620 |
| **Exchanges** | `L:2626 → L:2671` | `POST /api/exchanges/add` L:2630, `GET /api/exchanges/list` L:2650, `DELETE /api/exchanges/remove` L:2655, `POST /api/exchanges/test` L:2664 |
| **Risk & Monitoring** | `L:2673 → L:2748` | `GET /api/drawdown` L:2677, `POST /api/killswitch` L:2682, `GET /api/killswitch/status` L:2703, `GET /api/journal` L:2717, `GET /api/export/csv` L:2728 |
| **System** | `L:2750 → L:2793` | `GET /api/status` L:2754, `GET /` L:2785, `GET /<path>` L:2790 |
| **>>> INSÉRER ROUTE** | `L:2783` | **Nouvelle route → avant L:2785 (`@app.route("/")`)** |

---

### 1.7 RÉSUMÉ DES POINTS D'INSERTION PAR TYPE

```
┌─────────────────────────────────────────────────────────────────┐
│                    POINTS D'INSERTION                           │
├──────────────┬──────────────────┬───────────────────────────────┤
│ Type         │ Fichier          │ Insérer AVANT la ligne        │
├──────────────┼──────────────────┼───────────────────────────────┤
│ CSS          │ dashboard.html   │ L:1175  (</style>)            │
│ HTML         │ dashboard.html   │ L:1580  (<!-- Lightweight -->) │
│ JS function  │ dashboard.html   │ L:3142  (INIT ON DOM READY)   │
│ JS init call │ dashboard.html   │ L:3171  (startAutoRefresh)    │
│ API route    │ server.py        │ L:2785  (@app.route("/"))     │
│ Classe Python│ server.py        │ L:1828  (après PaperTrader)   │
│ Indicateur   │ server.py        │ L:618   (avant compute_all)   │
└──────────────┴──────────────────┴───────────────────────────────┘
```

---
