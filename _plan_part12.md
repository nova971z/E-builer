### ÉTAPE 10.0 — DARK/LIGHT MODE

**Commit cible** : `feat: step 38 — dark/light theme toggle with chart sync`

**Objectif** : Ajouter un toggle dark/light mode dans la navbar. Le thème light
redéfinit toutes les variables CSS `:root`, synchronise les couleurs des 3 charts
TradingView, et persiste en localStorage. Le mode dark actuel devient le défaut.
Transition fluide via `transition` sur `background-color` et `color`.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | **Aucun** — fonctionnalité 100% frontend | — |
| `dashboard.html` | CSS : variables light dans `[data-theme="light"]` | Après `:root` (`L:31`) |
| `dashboard.html` | CSS : transition globale pour le switch | Modifier `L:33` (reset `*`) |
| `dashboard.html` | HTML : bouton toggle dans navbar | Modifier `L:1192` (navbar-actions) |
| `dashboard.html` | JS : état global thème | Dans Global State après `L:1614` |
| `dashboard.html` | JS : `toggleTheme()` + sync charts | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : `chartOptions` / `subChartOptions` dynamiques | Modifier `L:1638` et `L:1723` |
| `dashboard.html` | JS : init thème dans DOMContentLoaded | Dans `L:3143` |

---

#### Sous-tâches

**10.1 — CSS : variables light** (`dashboard.html`)

- Insérer après `L:31` (après la fermeture de `:root`)
- Définir le thème light via l'attribut `data-theme` sur `<html>` :
```css
[data-theme="light"] {
    --bg: #f5f5f5;
    --surface: #ffffff;
    --surface-2: #f0f0f0;
    --surface-3: #e0e0e0;
    --border: #d9d9d9;
    --text: #1a1a1a;
    --text-dim: #555555;
    --text-muted: #999999;
    --green: #0a9e6a;
    --green-bg: rgba(10,158,106,0.1);
    --red: #d63a4a;
    --red-bg: rgba(214,58,74,0.1);
    --accent: #0090b3;
    --accent-bg: rgba(0,144,179,0.1);
    --yellow: #c99400;
    --yellow-bg: rgba(201,148,0,0.1);
    --orange: #cc7000;
}
```

**10.2 — CSS : transition fluide** (`dashboard.html`)

- Modifier `L:33` (le reset `*`)
- Ajouter `transition` pour les propriétés de couleur :
```css
*, *::before, *::after {
    margin: 0; padding: 0; box-sizing: border-box;
    transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
```

**10.3 — JS : constantes de thème pour les charts** (`dashboard.html`)

- Insérer après `L:1614` (fin du Global State)
```javascript
let currentTheme = localStorage.getItem('jarvis_theme') || 'dark';

var CHART_THEMES = {
    dark: {
        bg: '#0b0e11',
        text: '#848e9c',
        textMuted: '#5e6673',
        grid: 'rgba(43,49,57,0.5)',
        gridSub: 'rgba(43,49,57,0.3)',
        border: '#2b3139',
        crosshair: 'rgba(255,255,255,0.2)',
        watermark: 'rgba(0,212,255,0.04)',
    },
    light: {
        bg: '#ffffff',
        text: '#555555',
        textMuted: '#999999',
        grid: 'rgba(0,0,0,0.06)',
        gridSub: 'rgba(0,0,0,0.04)',
        border: '#d9d9d9',
        crosshair: 'rgba(0,0,0,0.15)',
        watermark: 'rgba(0,144,179,0.04)',
    }
};
```

**10.4 — JS : rendre `chartOptions` dynamique** (`dashboard.html`)

- Modifier `L:1638 → L:1670` (`chartOptions`)
- Remplacer les couleurs hardcodées par une fonction :
```javascript
function getChartOptions() {
    var t = CHART_THEMES[currentTheme];
    return {
        layout: { background: { color: t.bg }, textColor: t.text, fontSize: 11, fontFamily: "'SF Mono', 'Consolas', monospace" },
        grid: { vertLines: { color: t.grid }, horzLines: { color: t.grid } },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { color: t.crosshair, style: 0, width: 1 },
            horzLine: { color: t.crosshair, style: 0, width: 1 },
        },
        rightPriceScale: { borderColor: t.border, scaleMargins: { top: 0.05, bottom: 0.05 } },
        timeScale: { borderColor: t.border, timeVisible: true, secondsVisible: false },
        watermark: { visible: true, text: 'J.A.R.V.I.S.', fontSize: 48, color: t.watermark },
        handleScroll: { vertTouchDrag: false },
    };
}
var chartOptions = getChartOptions();
```

**10.5 — JS : rendre `subChartOptions` dynamique** (`dashboard.html`)

- Modifier `L:1723 → L:1733` (`subChartOptions`)
- Même pattern :
```javascript
function getSubChartOptions() {
    var t = CHART_THEMES[currentTheme];
    return {
        layout: { background: { color: t.bg }, textColor: t.textMuted, fontSize: 10 },
        grid: { vertLines: { color: t.gridSub }, horzLines: { color: t.gridSub } },
        rightPriceScale: { borderColor: t.border, scaleMargins: { top: 0.1, bottom: 0.1 } },
        timeScale: { visible: false },
        crosshair: { horzLine: { visible: false }, vertLine: { visible: false } },
        handleScroll: { vertTouchDrag: false },
    };
}
var subChartOptions = getSubChartOptions();
```

**10.6 — JS : `applyChartTheme()`** (`dashboard.html`)

- Insérer avant `L:3142`
- Synchronise les 3 charts TradingView avec le thème actif :
```javascript
function applyChartTheme() {
    var t = CHART_THEMES[currentTheme];
    var opts = getChartOptions();
    var subOpts = getSubChartOptions();
    if (mainChart) mainChart.applyOptions(opts);
    if (rsiChart) rsiChart.applyOptions(subOpts);
    if (macdChart) macdChart.applyOptions(subOpts);
}
```

**10.7 — JS : `toggleTheme()`** (`dashboard.html`)

- Insérer après `applyChartTheme()`
```javascript
function toggleTheme() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('jarvis_theme', currentTheme);
    applyChartTheme();
    var btn = $('btn-theme');
    if (btn) btn.textContent = currentTheme === 'dark' ? '☀' : '☾';
}
```

**10.8 — HTML : bouton toggle dans navbar** (`dashboard.html`)

- Modifier `L:1192` (`navbar-actions`)
- Ajouter avant le bouton son (étape 6.0) ou avant le bouton AI :
```html
<button class="btn-nav btn-theme" id="btn-theme" onclick="toggleTheme()">☀</button>
```

**10.9 — CSS : style du bouton thème** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
```css
.btn-theme { font-size: 16px; min-width: 32px; cursor: pointer; }
```

**10.10 — JS : init thème au chargement** (`dashboard.html`)

- Dans `DOMContentLoaded` (`L:3143`), ajouter EN TOUT PREMIER (avant `initMainChart`) :
```javascript
// Appliquer le thème sauvegardé
if (currentTheme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
}
var themeBtn = $('btn-theme');
if (themeBtn) themeBtn.textContent = currentTheme === 'dark' ? '☀' : '☾';
```
- Important : l'attribut `data-theme` doit être appliqué AVANT `initMainChart()`
  pour que les charts soient créés avec les bonnes couleurs dès le départ

**10.11 — Mise à jour `initMainChart()` et `initRSIChart()` / `initMACDChart()`**

- Modifier `initMainChart()` (`L:1673`) : remplacer `chartOptions` statique par `getChartOptions()`
```javascript
mainChart = LightweightCharts.createChart(container, {
    ...getChartOptions(),
    width: container.clientWidth,
    height: container.clientHeight,
});
```
- Modifier `initRSIChart()` (`L:1735`) et `initMACDChart()` (`L:1760`) : idem avec `getSubChartOptions()`

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V10.1 | Le bouton ☀/☾ apparaît dans la navbar | Navigateur |
| V10.2 | Cliquer bascule entre dark et light | Cliquer, observer le fond |
| V10.3 | En light : fond blanc, texte noir, borders grises | Vérifier visuellement |
| V10.4 | Les 3 charts (main, RSI, MACD) suivent le thème | Vérifier fond + grille des charts |
| V10.5 | Les couleurs vert/rouge restent lisibles en light | Comparer contraste |
| V10.6 | La transition est fluide (pas de flash) | Observer le switch |
| V10.7 | Le thème persiste au refresh (localStorage) | F5 en mode light, vérifier |
| V10.8 | Le watermark JARVIS est visible dans les deux thèmes | Zoom sur le chart |
| V10.9 | Les modals, toasts, alertes suivent le thème | Ouvrir Settings en light |
| V10.10 | Retour en dark mode fonctionne correctement | Re-cliquer le bouton |

---

#### Note de reprise

> Étape 100% frontend — aucune modification de `server.py`.
> Le principe : `[data-theme="light"]` sur `<html>` surcharge les variables `:root`.
> Toutes les couleurs du CSS utilisent déjà `var(--xxx)` — le switch est automatique.
> SAUF les charts TradingView qui ont des couleurs hardcodées en JS → `applyChartTheme()`
> les met à jour dynamiquement via l'API `chart.applyOptions()`.
> Le `chartOptions` et `subChartOptions` passent de `const` à `var` car ils sont
> maintenant retournés par des fonctions (`getChartOptions()`, `getSubChartOptions()`).
> L'init du thème DOIT être avant `initMainChart()` dans DOMContentLoaded.
> localStorage key : `jarvis_theme` (valeurs : `"dark"` / `"light"`).

---
