### ÉTAPE 7.0 — SPARKLINES (MINI-CHARTS SVG)

**Commit cible** : `feat: step 35 — sparkline mini-charts in ticker and asset bar`

**Objectif** : Ajouter des mini-courbes SVG (50×16px) à côté de chaque symbole dans
le ticker footer et dans l'asset bar. Chaque sparkline montre les 20 derniers
prix pour donner un aperçu visuel instantané de la tendance. Les données viennent
d'une nouvelle route API légère qui retourne des mini-séries.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Nouvelle route `GET /api/sparklines` | Avant `L:2785` (`@app.route("/")`) |
| `dashboard.html` | CSS : svg sparkline | Avant `L:1175` (`</style>`) |
| `dashboard.html` | JS : `buildSparklineSVG()` (pur SVG string) | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : modifier `loadTicker()` | Modifier `L:2202` |
| `dashboard.html` | JS : modifier `loadPriceData()` | Modifier `L:2248` |
| `dashboard.html` | HTML : placeholder dans asset bar | Modifier `L:1237` (avant asset-shortcuts) |

---

#### Sous-tâches

**7.1 — Route API `GET /api/sparklines`** (`server.py`)

- Insérer avant `L:2785`
- Pour chaque paire dans `["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT"]` :
  - Fetch klines 15m, limit=20 via `fetch_binance()` (cache TTL 30s)
  - Extraire uniquement les closes : `[float(k[4]) for k in raw]`
- Pour GOLD/SILVER : utiliser `fetch_stooq_price()` (un seul point, pas de sparkline)
- Retourner :
```json
{
  "BTCUSDT": [67000, 67120, 67050, 66980, ...],
  "ETHUSDT": [3520, 3515, 3530, 3542, ...],
  "SOLUSDT": [145.2, 144.8, 145.5, ...],
  "XRPUSDT": [0.512, 0.515, 0.511, ...],
  "DOGEUSDT": [0.155, 0.156, 0.154, ...]
}
```
- Cache TTL = 30s (aligner avec le refresh ticker)

**7.2 — JS : `buildSparklineSVG(prices, width, height, color)`** (`dashboard.html`)

- Insérer avant `L:3142`
- Fonction pure qui retourne un string HTML `<svg>...</svg>`
- Paramètres par défaut : `width=50, height=16, color='var(--accent)'`
- Algorithme :
  - Si `prices.length < 2` : retourner chaîne vide
  - Trouver min/max des prix
  - Normaliser chaque point : `x = i * (width / (len-1))`, `y = height - ((p - min) / (max - min)) * height`
  - Construire un attribut `points` pour `<polyline>`
  - Couleur : `--green` si dernier > premier, `--red` si dernier < premier, `--accent` sinon
```javascript
function buildSparklineSVG(prices, width, height, color) {
    if (!prices || prices.length < 2) return '';
    width = width || 50;
    height = height || 16;
    var min = Math.min.apply(null, prices);
    var max = Math.max.apply(null, prices);
    var range = max - min || 1;
    if (!color) color = prices[prices.length-1] >= prices[0] ? 'var(--green)' : 'var(--red)';
    var pts = '';
    for (var i = 0; i < prices.length; i++) {
        var x = (i / (prices.length - 1)) * width;
        var y = height - ((prices[i] - min) / range) * (height - 2) - 1;
        pts += x.toFixed(1) + ',' + y.toFixed(1) + ' ';
    }
    return '<svg class="sparkline" viewBox="0 0 ' + width + ' ' + height
        + '" width="' + width + '" height="' + height + '">'
        + '<polyline points="' + pts.trim() + '" fill="none" stroke="' + color
        + '" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}
```

**7.3 — JS : variable globale sparkline data** (`dashboard.html`)

- Insérer après `L:1614` (fin de `indicatorState`)
```javascript
let sparklineData = {};
```

**7.4 — JS : `loadSparklines()`** (`dashboard.html`)

- Insérer après `buildSparklineSVG()`
- Fetch `GET /api/sparklines`
- Stocker dans `sparklineData`
- Appelée depuis `loadTicker()` quand les données sont vides ou toutes les 30s

**7.5 — JS : modifier `loadTicker()` pour injecter les sparklines** (`dashboard.html`)

- Modifier `L:2212 → L:2224` (boucle de rendu du ticker footer)
- Après le prix et le changement %, ajouter l'appel SVG :
```javascript
html += '<span class="ft-ticker-item">'
    + '<span class="sym">' + t.symbol + '</span>'
    + buildSparklineSVG(sparklineData[t.symbol], 40, 14)
    + '<span class="val ' + cls + '">' + fmt(parseFloat(t.price)) + ' ' + sign + parseFloat(t.change_pct).toFixed(2) + '%</span>'
    + '</span>';
```

**7.6 — HTML : placeholder sparkline dans asset bar** (`dashboard.html`)

- Modifier `L:1237` — ajouter un `<span>` avant les asset-shortcuts :
```html
<div class="asset-sparkline" id="asset-sparkline"></div>
<div class="asset-shortcuts">
```

**7.7 — JS : modifier `loadPriceData()` pour mettre à jour l'asset sparkline** (`dashboard.html`)

- Modifier `loadPriceData()` (`L:2248`)
- Après les stats existantes, ajouter :
```javascript
var sparkEl = $('asset-sparkline');
if (sparkEl && sparklineData[symbol]) {
    sparkEl.innerHTML = buildSparklineSVG(sparklineData[symbol], 80, 24);
}
```

**7.8 — CSS sparkline** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
```css
.sparkline {
    vertical-align: middle;
    opacity: 0.85;
}
.ft-ticker-item .sparkline {
    margin: 0 2px;
}
.asset-sparkline {
    display: flex;
    align-items: center;
    margin: 0 8px;
}
.asset-sparkline .sparkline {
    width: 80px;
    height: 24px;
}
```

**7.9 — Intégration refresh** (`dashboard.html`)

- Dans `startAutoRefresh()` (`L:3079`) : appeler `loadSparklines()` dans l'intervalle 30s du ticker (~L:3087)
- Dans `DOMContentLoaded` (`L:3143`) : appeler `loadSparklines()` après `loadTicker()`
- Dans `changeSymbol()` (`L:2020`) : mettre à jour `#asset-sparkline`

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V7.1 | `python3 -m py_compile server.py` passe | Terminal |
| V7.2 | `GET /api/sparklines` retourne 5 tableaux de 20 prix | `curl` |
| V7.3 | Les sparklines s'affichent dans le ticker footer | Navigateur, regarder le bandeau bas |
| V7.4 | Couleur verte si tendance haussière, rouge si baissière | Comparer direction vs couleur |
| V7.5 | La sparkline apparaît dans l'asset bar | Regarder à côté du prix principal |
| V7.6 | Changer de symbole met à jour l'asset sparkline | Cliquer BTC → ETH |
| V7.7 | Les SVG sont nets (pas de pixelisation) | Zoom navigateur 200% |
| V7.8 | Auto-refresh toutes les 30s fonctionne | Attendre, observer changement |

---

#### Note de reprise

> Étape légère — 1 route API simple + 1 fonction SVG pure + intégration dans
> 2 fonctions existantes (`loadTicker`, `loadPriceData`).
> Le SVG est construit comme un string HTML (pas `document.createElementNS`).
> Les données sparkline sont cachées 30s côté serveur et stockées dans
> `sparklineData` côté client pour éviter les refetch inutiles.
> GOLD/SILVER n'auront pas de sparkline (Stooq ne fournit qu'un prix spot).
> La fonction `buildSparklineSVG` est réutilisable pour l'étape 8.0 (Heatmap).

---
