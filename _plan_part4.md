### ÉTAPE 2.0 — PORTFOLIO TRACKER & EQUITY CURVE

**Commit cible** : `feat: step 30 — portfolio tracker & equity curve`

**Objectif** : Vue portefeuille complète avec PnL cumulé, allocation par symbole
(pie chart SVG), et courbe d'equity historique (line chart TradingView) basée
sur l'historique des paper trades. Accessible via un onglet du Bottom Panel.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Nouvelle route `GET /api/portfolio` | Avant `L:2785` (`@app.route("/")`) |
| `server.py` | Nouvelle route `GET /api/equity-curve` | Avant `L:2785` (`@app.route("/")`) |
| `dashboard.html` | CSS du portfolio | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML onglet Portfolio dans Bottom Panel | Modifier `L:1318` zone `.bp-tabs` |
| `dashboard.html` | JS : fetch + render + SVG pie | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : appel init | Dans `DOMContentLoaded` `L:3143` |

---

#### Sous-tâches

**2.1 — Route API `GET /api/portfolio`** (`server.py`)

- Insérer avant `L:2785`
- Requête SQL sur `paper_trades` (status = 'closed') :
  - Grouper par `symbol` → total PnL par symbole, nombre de trades, win rate
  - Calculer PnL cumulé global
  - Calculer allocation = PnL par symbole / PnL total (pour pie chart)
- Requête SQL sur `paper_trades` (status = 'open') :
  - Positions ouvertes actuelles avec unrealized PnL estimé
- Retourner :
```json
{
  "total_pnl": 125.40,
  "total_trades": 34,
  "win_rate": 62.5,
  "open_positions": 2,
  "unrealized_pnl": -12.30,
  "by_symbol": [
    {"symbol": "BTCUSDT", "pnl": 89.20, "trades": 18, "win_rate": 66.7, "pct": 71.1},
    {"symbol": "ETHUSDT", "pnl": 36.20, "trades": 16, "win_rate": 56.3, "pct": 28.9}
  ],
  "best_trade": {"symbol": "BTCUSDT", "pnl": 42.10, "date": "2026-04-18"},
  "worst_trade": {"symbol": "ETHUSDT", "pnl": -18.50, "date": "2026-04-15"}
}
```

**2.2 — Route API `GET /api/equity-curve`** (`server.py`)

- Insérer juste après la route portfolio (avant `L:2785`)
- Requête SQL : `SELECT closed_at, pnl FROM paper_trades WHERE status='closed' ORDER BY closed_at ASC`
- Calculer le PnL cumulé chronologique :
  - Commencer au capital initial (`get_setting('paper_capital', '100')`)
  - Pour chaque trade fermé : `equity += pnl`
  - Retourner tableau `[{time: epoch, value: equity}, ...]`
- Format compatible TradingView `LineSeries` :
```json
{
  "initial_capital": 100,
  "current_equity": 225.40,
  "curve": [
    {"time": 1713400000, "value": 100},
    {"time": 1713450000, "value": 112.30},
    {"time": 1713500000, "value": 108.10}
  ]
}
```

**2.3 — CSS du Portfolio** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Classes à créer :
  - `.portfolio-wrap` — conteneur flex horizontal (pie + stats)
  - `.portfolio-stats` — colonne gauche : total PnL, win rate, trades count
  - `.portfolio-stat` — une ligne stat (label + value), réutiliser style `.wallet-row`
  - `.portfolio-pie` — conteneur SVG 120×120px pour le pie chart
  - `.portfolio-legend` — légende couleurs sous le pie
  - `.equity-chart-wrap` — conteneur pour le mini line chart equity (hauteur 150px)
- Couleurs : utiliser palette tournante `--green`, `--accent`, `--yellow`, `--red`, `#9b59b6`, `#e67e22`

**2.4 — HTML : onglet Portfolio dans Bottom Panel** (`dashboard.html`)

- Modifier la zone `.bp-tabs` (`L:1318 → L:1325`)
- Ajouter un bouton entre "Paper Trades" et "Journal" :
```html
<button onclick="switchBPTab('portfolio')">Portfolio</button>
```
- Le contenu sera rendu dynamiquement dans `#bp-content` par JS

**2.5 — JS : fonction `loadPortfolio()`** (`dashboard.html`)

- Insérer avant `L:3142` (`// INIT ON DOM READY`)
- Fetch `GET /api/portfolio`
- Générer le HTML dans `#bp-content` :
  - Section stats : Total PnL (coloré vert/rouge), Win Rate %, Total Trades, Open Positions
  - Best/Worst trade
- Appeler `renderPieChart()` avec les données `by_symbol`

**2.6 — JS : fonction `renderPieChart(data)`** (`dashboard.html`)

- Insérer juste après `loadPortfolio()`
- Générer un SVG inline (pas de librairie externe) :
  - `<svg viewBox="0 0 120 120">` avec arcs `<path>` pour chaque symbole
  - Calcul des arcs via `Math.cos` / `Math.sin` et coordonnées polaires
  - Légende sous le SVG : pastille couleur + symbole + pourcentage
- Fonction pure : prend un tableau `[{symbol, pct, pnl}]`, retourne un string HTML

**2.7 — JS : fonction `loadEquityCurve()`** (`dashboard.html`)

- Insérer juste après `renderPieChart()`
- Fetch `GET /api/equity-curve`
- Créer un mini chart TradingView `createChart()` dans un div `#equity-chart`
  - Hauteur 150px, même thème que `subChartOptions` (L:1723)
  - `LineSeries` avec couleur `--accent`
  - Données = `curve` de la réponse API
- Appelée depuis `loadPortfolio()` après le render des stats

**2.8 — Intégration `switchBPTab()`** (`dashboard.html`)

- Modifier `switchBPTab()` (`L:2373`) :
  - Ajouter `case 'portfolio': loadPortfolio(); break;`
- Dans `DOMContentLoaded` : ne pas appeler `loadPortfolio()` au démarrage (chargement à la demande seulement)

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V2.1 | `python3 -m py_compile server.py` passe | Commande terminal |
| V2.2 | `GET /api/portfolio` retourne PnL et by_symbol | `curl` |
| V2.3 | `GET /api/equity-curve` retourne un tableau curve[] | `curl` |
| V2.4 | L'onglet "Portfolio" apparaît dans le Bottom Panel | Navigateur |
| V2.5 | Cliquer l'onglet affiche stats + pie chart SVG | Navigateur |
| V2.6 | Le pie chart reflète les proportions par symbole | Comparer pct vs arc visuel |
| V2.7 | L'equity curve s'affiche en line chart | Navigateur |
| V2.8 | Avec 0 trades fermés, affichage "No trades yet" | Tester sur DB vide |

---

#### Note de reprise

> Dépendance : cette étape utilise la table `paper_trades` (L:160 server.py).
> Pas besoin de modifier le schéma DB — toutes les colonnes nécessaires existent
> déjà (`symbol`, `side`, `entry_price`, `exit_price`, `pnl`, `status`, `closed_at`).
> Le pie chart est en SVG pur — pas de dépendance externe.
> L'equity curve réutilise TradingView `createChart` (déjà chargé via `lw-charts.js`).

---
