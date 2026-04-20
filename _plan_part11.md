### ÉTAPE 9.0 — RESPONSIVE MOBILE

**Commit cible** : `feat: step 37 — responsive layout for tablet and mobile`

**Objectif** : Rendre le dashboard utilisable sur tablette (768-1024px) et mobile
(<768px). Le layout 3 colonnes se transforme en colonne unique avec le right panel
en slide-over. Un bouton hamburger dans la navbar pilote la navigation mobile.
Le chart reste prioritaire. Aucun changement de HTML structurel majeur — uniquement
des media queries CSS et un toggle JS minimal.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | **Aucun** — fonctionnalité 100% CSS/JS frontend | — |
| `dashboard.html` | Meta viewport | Déjà présent `L:5` ✓ |
| `dashboard.html` | CSS : media queries tablette + mobile | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML : bouton hamburger dans navbar | Modifier `L:1191` (avant navbar-spacer) |
| `dashboard.html` | HTML : overlay backdrop pour slide-over | Après `L:1448` (`</div><!-- /main-layout -->`) |
| `dashboard.html` | JS : `toggleMobilePanel()` | Avant `L:3142` (`// INIT ON DOM READY`) |

---

#### Sous-tâches

**9.1 — HTML : bouton hamburger** (`dashboard.html`)

- Modifier `L:1191` — ajouter avant `<div class="navbar-spacer">` :
```html
<button class="btn-nav btn-hamburger" id="btn-hamburger" onclick="toggleMobilePanel()">&#9776;</button>
```
- Masqué par défaut en desktop (CSS), visible en mobile

**9.2 — HTML : overlay backdrop** (`dashboard.html`)

- Insérer après `L:1448` (`</div><!-- /main-layout -->`) :
```html
<div class="mobile-overlay" id="mobile-overlay" onclick="toggleMobilePanel()"></div>
```

**9.3 — CSS : variables responsive** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Ajouter les styles de base pour le hamburger et l'overlay :
```css
.btn-hamburger { display: none; font-size: 18px; }
.mobile-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 149;
}
.mobile-overlay.visible { display: block; }
```

**9.4 — CSS : media query TABLETTE (768px → 1024px)** (`dashboard.html`)

- Insérer après les styles de base (avant `</style>`)
```css
@media (max-width: 1024px) {
    /* Navbar : cacher les liens texte, garder les boutons */
    .navbar-menu a { font-size: 10px; padding: 4px 6px; }

    /* Drawing toolbar : cacher (trop petit pour dessiner) */
    .draw-toolbar { display: none; }

    /* Right panel : réduire à 240px */
    .right-panel { width: 240px; min-width: 240px; }

    /* Order form : réduire les paddings */
    .order-form { padding: 6px; }
    .of-type-tabs button { font-size: 9px; padding: 3px 4px; }

    /* Asset bar : masquer OI et Funding */
    .asset-stat:nth-child(n+6) { display: none; }

    /* Footer : réduire */
    .ft-info span:nth-child(n+4) { display: none; }

    /* JARVIS chat : pleine largeur en bas */
    .jarvis-chat { width: 300px; right: 8px; }
}
```

**9.5 — CSS : media query MOBILE (<768px)** (`dashboard.html`)

- Insérer après la media query tablette
```css
@media (max-width: 768px) {
    /* Hamburger visible */
    .btn-hamburger { display: flex; }

    /* Navbar : compacter */
    .navbar-menu { display: none; }
    .navbar-logo span { display: none; }
    .navbar-clock { display: none; }

    /* Asset bar : scroll horizontal, masquer stats secondaires */
    .asset-bar { overflow-x: auto; gap: 6px; padding: 4px 8px; }
    .asset-stat:nth-child(n+4) { display: none; }
    .asset-shortcuts { display: none; }

    /* Heatmap bar (étape 8.0) : masquer texte, garder couleurs */
    .hm-cell .hm-sym { display: none; }
    .hm-cell { min-width: 30px; font-size: 8px; }

    /* Main layout : colonne unique */
    .main-layout {
        flex-direction: column;
        height: auto;
        overflow-y: auto;
    }

    /* Chart area : hauteur fixe adaptée */
    .chart-area {
        border-right: none;
        border-bottom: 1px solid var(--border);
        height: 50vh;
        min-height: 300px;
    }

    /* Sub-charts : plus compacts */
    .subchart-wrap { height: 60px; min-height: 60px; }

    /* Drawing toolbar : masquer */
    .draw-toolbar { display: none; }

    /* Right panel : slide-over depuis la droite */
    .right-panel {
        position: fixed;
        top: 48px;
        right: -300px;
        width: 280px;
        height: calc(100vh - 48px - 28px);
        z-index: 150;
        transition: right 0.25s ease;
        border-left: 1px solid var(--border);
        overflow-y: auto;
    }
    .right-panel.open { right: 0; }

    /* Bottom panel : scroll horizontal pour les tabs */
    .bp-tabs { overflow-x: auto; flex-wrap: nowrap; }
    .bp-tabs button { white-space: nowrap; font-size: 10px; }

    /* Footer : simplifier */
    .footer { height: 24px; font-size: 9px; gap: 6px; }
    .ft-ticker { display: none; }
    .ft-info span:nth-child(n+3) { display: none; }

    /* JARVIS chat : plein écran mobile */
    .jarvis-chat {
        width: 100%;
        height: calc(100vh - 80px);
        bottom: 28px;
        right: 0;
        border-radius: 0;
    }

    /* Modals : pleine largeur */
    .modal { width: 95vw; max-height: 85vh; }
}
```

**9.6 — CSS : media query PETIT MOBILE (<480px)** (`dashboard.html`)

- Insérer après la media query mobile
```css
@media (max-width: 480px) {
    .navbar { padding: 0 6px; gap: 4px; }
    .btn-nav { padding: 4px 6px; font-size: 10px; }
    .chart-area { height: 40vh; min-height: 250px; }
    .asset-bar { height: auto; flex-wrap: wrap; }
    .asset-stat:nth-child(n+3) { display: none; }
    .right-panel { width: 100%; right: -100%; }
    .right-panel.open { right: 0; }
}
```

**9.7 — JS : `toggleMobilePanel()`** (`dashboard.html`)

- Insérer avant `L:3142`
```javascript
function toggleMobilePanel() {
    var panel = document.querySelector('.right-panel');
    var overlay = $('mobile-overlay');
    if (!panel) return;
    var isOpen = panel.classList.contains('open');
    panel.classList.toggle('open');
    if (overlay) overlay.classList.toggle('visible');
    // Empêcher scroll du body quand panel ouvert
    document.body.style.overflow = isOpen ? '' : 'hidden';
}
```

**9.8 — JS : fermer le panel au changement de symbole** (`dashboard.html`)

- Modifier `changeSymbol()` (`L:2020`)
- Ajouter en fin de fonction :
```javascript
// Fermer le panel mobile si ouvert
var panel = document.querySelector('.right-panel');
if (panel && panel.classList.contains('open')) toggleMobilePanel();
```

**9.9 — JS : resize handler pour cleanup** (`dashboard.html`)

- Insérer après `toggleMobilePanel()`
- Si l'utilisateur passe de mobile à desktop (resize fenêtre) :
```javascript
window.addEventListener('resize', function() {
    if (window.innerWidth > 768) {
        var panel = document.querySelector('.right-panel');
        var overlay = $('mobile-overlay');
        if (panel) panel.classList.remove('open');
        if (overlay) overlay.classList.remove('visible');
        document.body.style.overflow = '';
    }
});
```

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V9.1 | Desktop (>1024px) : aucun changement visuel | Ouvrir en plein écran |
| V9.2 | Tablette (768-1024px) : right panel réduit, stats masquées | DevTools responsive 800px |
| V9.3 | Mobile (<768px) : layout colonne unique | DevTools responsive 375px |
| V9.4 | Le hamburger ☰ apparaît en mobile | Vérifier navbar à 375px |
| V9.5 | Cliquer ☰ ouvre le right panel en slide-over | Tester le toggle |
| V9.6 | L'overlay assombrit le fond quand panel ouvert | Observer le backdrop |
| V9.7 | Cliquer l'overlay ferme le panel | Cliquer hors du panel |
| V9.8 | Le chart occupe ~50% de l'écran mobile | Vérifier la hauteur |
| V9.9 | Les modals sont pleine largeur en mobile | Ouvrir Settings à 375px |
| V9.10 | Resize desktop→mobile→desktop ne casse rien | Redimensionner la fenêtre |

---

#### Note de reprise

> Étape 100% frontend — aucune modification de `server.py`.
> Le `<meta viewport>` existe déjà (`L:5`).
> Les media queries utilisent uniquement `max-width` (mobile-first inversé).
> Le right panel passe en `position: fixed` + slide-over en mobile.
> Le `overflow: hidden` sur body empêche le double-scroll.
> Si l'étape 8.0 (Heatmap) n'est pas encore implémentée, les règles `.hm-cell`
> seront simplement ignorées (pas d'erreur CSS).
> Ne jamais mettre `display: none` sur `.chart-area` — le chart doit toujours
> être visible, c'est la pièce centrale du dashboard.

---
