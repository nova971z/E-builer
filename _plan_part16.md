## 6. NOTES DE REPRISE INTER-SESSION & STRATÉGIE DE RECOVERY

> **Ce fichier est la première chose à lire en début de session.**
> Si le contexte conversationnel a été perdu (nouvelle session, compression,
> timeout), cette section contient tout ce qu'il faut pour reprendre.

---

### 6.1 PROCÉDURE DE REPRISE (EXÉCUTER À CHAQUE DÉBUT DE SESSION)

```
ÉTAPE 1 — Identifier où on en est
    Lire PLAN.md section 4.1 (tableau de suivi global)
    → Trouver la dernière étape marquée [x] FAIT
    → L'étape suivante est celle à faire

ÉTAPE 2 — Vérifier l'état du code
    git status
    → S'il y a des modifications non commitées, les analyser avant de continuer
    git log --oneline -5
    → Vérifier le dernier commit (quel step ?)

ÉTAPE 3 — Lire l'étape à faire
    Lire PLAN.md section de l'étape concernée (chercher "### ÉTAPE X.0")
    → Lire l'objectif, les fichiers touchés, les sous-tâches

ÉTAPE 4 — Vérifier la carte de navigation
    Lire PLAN.md section 1 (carte de navigation)
    → Les numéros de ligne ont pu changer après les étapes précédentes
    → Utiliser les ANCRES TEXTUELLES plutôt que les numéros de ligne

ÉTAPE 5 — Commencer
    Marquer l'étape EN COURS dans le tableau de suivi
    Coder la première sous-tâche
```

---

### 6.2 ANCRES TEXTUELLES DE RÉFÉRENCE

Les numéros de ligne bougent à chaque étape. Ces chaînes de texte, elles,
ne bougent JAMAIS. Les utiliser pour se repérer avec `grep -n` :

```bash
# Points d'insertion CSS
grep -n "</style>" dashboard.html              # → fin du CSS

# Points d'insertion HTML
grep -n "<!-- MAIN LAYOUT -->" dashboard.html  # → début du layout
grep -n "<!-- /main-layout -->" dashboard.html # → fin du layout (après chart+panels)
grep -n "<!-- FOOTER -->" dashboard.html       # → début du footer
grep -n "<!-- Lightweight Charts -->" dashboard.html # → fin du HTML body

# Points d'insertion JS
grep -n "GLOBAL STATE" dashboard.html          # → variables globales
grep -n "INIT ON DOM READY" dashboard.html     # → fin du JS (avant init)
grep -n "AUTO-REFRESH" dashboard.html          # → bloc des timers

# Points d'insertion server.py
grep -n '@app.route("/")' server.py            # → dernière route avant main
grep -n 'if __name__' server.py                # → entry point
grep -n 'def init_db' server.py                # → création des tables
```

---

### 6.3 COMMANDE DE DIAGNOSTIC RAPIDE POUR REPRENDRE

Copier-coller cette commande en début de session pour un état complet :

```bash
echo "=== GIT ===" && \
git branch --show-current && \
git log --oneline -3 && \
git status --short && \
echo "=== FICHIERS ===" && \
wc -l server.py dashboard.html PLAN.md 2>/dev/null && \
echo "=== ROUTES ===" && \
grep -c "@app.route" server.py && \
echo "=== FONCTIONS JS ===" && \
grep -c "^function \|^async function " dashboard.html && \
echo "=== SYNTAXE ===" && \
python3 -m py_compile server.py 2>&1 && echo "server.py OK" || echo "server.py ERREUR"
```

---

### 6.4 TABLE DE CORRESPONDANCE RAPIDE

Pour retrouver instantanément quelle étape correspond à quoi :

```
QUOI CHERCHER                    → OÙ DANS PLAN.MD
─────────────────────────────────────────────────────
Où en est-on ?                   → Section 4.1 (suivi global)
Quoi faire maintenant ?          → Section 3.4 (ordre d'exécution)
Détail d'une étape ?             → Chercher "### ÉTAPE X.0"
Où insérer du CSS ?              → Section 1.2 + ancre "</style>"
Où insérer du HTML ?             → Section 1.3 + ancre "<!-- Lightweight Charts -->"
Où insérer du JS ?               → Section 1.4 + ancre "INIT ON DOM READY"
Où insérer une route ?           → Section 1.6 + ancre '@app.route("/")'
Comment tester ?                 → Section 5 (checklist + protocoles)
Quelles dépendances ?            → Section 3.1 (matrice)
```

---

### 6.5 STRATÉGIE DE RECOVERY EN CAS DE PROBLÈME

#### Cas 1 : Le dashboard ne se charge plus (écran blanc)

```
1. Ouvrir la console DevTools (F12)
2. Lire la première erreur rouge
3. Cas fréquent : erreur de syntaxe JS → chercher la ligne indiquée
4. Si le problème est dans les dernières modifications :
   git diff HEAD~1 dashboard.html | head -50
   → Voir ce qui a changé
5. En dernier recours :
   git stash
   → Revenir à l'état propre, ouvrir le dashboard, vérifier que ça marche
   git stash pop
   → Réappliquer les changements et corriger
```

#### Cas 2 : Le serveur ne démarre pas (traceback Python)

```
1. Lire le traceback — la dernière ligne donne le fichier et la ligne
2. python3 -m py_compile server.py
   → Donne la ligne exacte de l'erreur de syntaxe
3. Si c'est une ImportError : vérifier requirements.txt et pip install
4. Si c'est une erreur SQLite : supprimer jarvis.db et relancer
   (init_db() recrée les tables automatiquement)
```

#### Cas 3 : Une étape a cassé une feature existante

```
1. Identifier la feature cassée
2. git log --oneline -5 → quel step a été fait en dernier ?
3. git diff HEAD~1 → voir les changements
4. Chercher dans le diff les modifications de fonctions existantes
5. La cause est presque toujours :
   - Variable renommée ou supprimée
   - Fonction modifiée avec un bug
   - ID d'élément HTML changé
6. Corriger le bug DANS L'ÉTAPE EN COURS (pas de nouveau commit)
7. Re-tester la régression (Section 5.3)
```

#### Cas 4 : Le PLAN.md a des numéros de ligne obsolètes

```
1. Les numéros de ligne bougent après chaque insertion
2. Ne JAMAIS se fier uniquement aux numéros — utiliser les ancres (Section 6.2)
3. Pour recalculer : grep -n "<ancre>" dashboard.html
4. Mettre à jour la section 1 (carte de navigation) avec les nouvelles valeurs
5. Commiter la mise à jour du PLAN.md avec l'étape
```

#### Cas 5 : Confusion sur quelle étape faire

```
1. Lire Section 4.1 → dernière étape [x]
2. Lire Section 3.4 → ordre d'exécution optimal
3. L'étape suivante est la prochaine non-cochée dans l'ordre de la Section 3.4
4. En cas de doute, demander à l'utilisateur :
   "La dernière étape terminée est X.0. Je fais Y.0 maintenant ?"
```

---

### 6.6 FICHIERS À NE JAMAIS PERDRE

| Fichier | Criticité | Recovery si perdu |
|---------|-----------|-------------------|
| `PLAN.md` | HAUTE | Récupérer depuis GitHub (pushé à chaque étape) |
| `server.py` | CRITIQUE | Récupérer depuis GitHub |
| `dashboard.html` | CRITIQUE | Récupérer depuis GitHub |
| `lw-charts.js` | HAUTE | Re-télécharger TradingView Lightweight Charts v4.2.1 |
| `jarvis.db` | BASSE | `init_db()` recrée les tables (données perdues OK en dev) |
| `secret.key` | MOYENNE | Régénéré automatiquement au premier lancement |

---

### 6.7 RÉSUMÉ EN UNE PHRASE PAR ÉTAPE

Pour se rappeler rapidement de quoi parle chaque étape :

```
 1.0  MTF        Panneau montrant RSI/MACD/régime sur 4 timeframes simultanés
 2.0  Portfolio   PnL cumulé + pie chart SVG + equity curve TradingView
 3.0  Alertes     CRUD alertes prix/indicateurs + toasts empilables + badge navbar
 4.0  Drawing     Canvas overlay sur le chart pour dessiner lignes/fib/rectangles
 5.0  Orders      OCO, Trailing, Iceberg, DCA dans le formulaire d'ordre
 6.0  Sons        7 sons synthétiques Web Audio API + toggle mute localStorage
 7.0  Sparklines  Mini SVG polyline 50×16px dans le ticker footer et asset bar
 8.0  Heatmap     Bande de cellules colorées vert/rouge entre asset bar et chart
 9.0  Responsive  Media queries 1024/768/480px + right panel slide-over + hamburger
10.0  Dark/Light  Variables CSS light + sync charts TradingView + localStorage toggle
```

---
