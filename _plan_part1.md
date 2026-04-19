# PLAN.md — J.A.R.V.I.S. Trading System v3.0 — Roadmap & Navigation

> **Fichier persistant** — Ce fichier est la source de vérité pour toutes les tâches
> d'amélioration du dashboard. Il survit aux compressions de contexte et aux
> changements de session. **Toujours le relire avant de commencer une étape.**

---

## 0. RÈGLES ANTI-PERTE DE MÉMOIRE

### 0.1 Protocole de début d'étape

Avant de coder quoi que ce soit, exécuter systématiquement :

```
1. Lire PLAN.md (ce fichier) — section de l'étape concernée
2. Lire les coordonnées de navigation (Section 2) pour localiser les zones d'insertion
3. Vérifier le statut de l'étape dans le tableau de suivi (Section 5)
4. Marquer l'étape [EN COURS] dans le tableau de suivi
```

### 0.2 Protocole de fin d'étape

Après chaque étape terminée :

```
1. Vérifier la syntaxe : python3 -m py_compile server.py (si server.py modifié)
2. Mettre à jour les coordonnées de navigation (Section 2) avec les nouveaux numéros de ligne
3. Marquer l'étape [FAIT] dans le tableau de suivi (Section 5)
4. Commit avec message : feat: step XX — <description courte>
5. Push sur la branche : git push -u origin claude/jarvis-trading-dashboard-HGW7A
```

### 0.3 Règles de numérotation

| Élément | Format | Exemple |
|---------|--------|---------|
| Étape principale | `X.0` | `1.0 Multi-Timeframe Analysis` |
| Sous-tâche | `X.Y` | `1.3 Ajouter la route API` |
| Sous-sous-tâche | `X.Y.Z` | `1.3.2 Gérer le cache TTL` |
| Commit | `step XX` | `feat: step 29 — multi-timeframe analysis panel` |
| Numéro de ligne | `L:NNN` | `dashboard.html L:1288` |

### 0.4 Conventions de code

| Règle | Détail |
|-------|--------|
| Python | Pas de numpy/pandas — calculs pure Python |
| JS | `function` declarations uniquement, pas de arrow functions |
| CSS | Variables dans `:root`, inline dans `<style>` de dashboard.html |
| Insertion CSS | Toujours AVANT `</style>` (repère : `dashboard.html L:1175`) |
| Insertion HTML | Identifier la zone exacte via Section 2 |
| Insertion JS | Toujours AVANT `// ========== INIT ON DOM READY ==========` (repère : `dashboard.html L:3142`) |
| Insertion route | Toujours AVANT `@app.route("/")` (repère : `server.py L:2785`) |
| Fichiers | Ne jamais créer de nouveau fichier .py ou .js — architecture single-file |
| Indicateurs | Pas de dépendances lourdes — tout en pure Python |

### 0.5 Stratégie de navigation rapide

Chaque étape de ce plan contient des **coordonnées d'insertion** au format :

```
INSERTION CSS  → dashboard.html L:1173  (avant </style>)
INSERTION HTML → dashboard.html L:XXXX  (zone spécifique documentée)
INSERTION JS   → dashboard.html L:3141  (avant INIT ON DOM READY)
INSERTION ROUTE → server.py L:2783      (avant la route "/")
```

Ces coordonnées sont mises à jour après chaque étape dans la **Section 2 — Carte de Navigation**.
Quand les lignes bougent après une insertion, recalculer le décalage :
`nouvelle_ligne = ancienne_ligne + nombre_de_lignes_ajoutées_avant`

### 0.6 Fichiers du projet (ne jamais modifier cette liste)

| Fichier | Rôle | Modifiable |
|---------|------|------------|
| `server.py` | Backend Flask unique | OUI |
| `dashboard.html` | Frontend SPA unique | OUI |
| `lw-charts.js` | TradingView Charts v4.2.1 vendored | NON |
| `CLAUDE.md` | Conventions Claude Code | OUI (référence PLAN.md) |
| `PLAN.md` | Ce fichier — roadmap & navigation | OUI (mise à jour après chaque étape) |
| `requirements.txt` | Dépendances Python | OUI (si nouvelle dep légère) |
| `scripts/*.sh` | Scripts opérationnels | OUI (si nouvelle route à tester) |

### 0.7 Numérotation des commits

Les 28 premiers steps (commits existants) couvrent la construction initiale.
Les nouvelles étapes d'amélioration commencent à **step 29** :

| Commit | Étape | Feature |
|--------|-------|---------|
| step 29 | 1.0 | Multi-Timeframe Analysis |
| step 30 | 2.0 | Portfolio Tracker & Equity Curve |
| step 31 | 3.0 | Alertes & Notifications |
| step 32 | 4.0 | Drawing Tools |
| step 33 | 5.0 | Advanced Order Types |
| step 34 | 6.0 | Effets Sonores |
| step 35 | 7.0 | Sparklines |
| step 36 | 8.0 | Heatmap |
| step 37 | 9.0 | Responsive Mobile |
| step 38 | 10.0 | Dark/Light Mode |

---
