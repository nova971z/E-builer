## 5. CHECKLIST POST-IMPLÉMENTATION & PROTOCOLES DE TEST

---

### 5.1 CHECKLIST À EXÉCUTER APRÈS CHAQUE ÉTAPE

Avant de marquer une étape comme terminée dans le tableau de suivi (Section 4),
exécuter cette checklist dans l'ordre :

```
□  1. SYNTAXE PYTHON
     python3 -m py_compile server.py
     → Doit retourner 0 (aucune erreur)
     → Si pas de modif server.py, ignorer

□  2. SYNTAXE HTML/JS
     Ouvrir dashboard.html dans le navigateur
     → Console DevTools : 0 erreurs JS
     → Pas de texte cassé / éléments manquants

□  3. DÉMARRAGE SERVEUR
     python3 server.py
     → Le serveur démarre sur port 5000 sans traceback
     → Le log affiche "J.A.R.V.I.S. Trading System vX.X starting"

□  4. HEALTH CHECK (si serveur tourne)
     ./scripts/health-check.sh
     → Toutes les routes existantes répondent 200 ou 502 (proxy externe)
     → Les nouvelles routes de l'étape répondent 200

□  5. CODE REVIEW AUTOMATISÉE
     ./scripts/code-review.sh
     → 0 issues critiques
     → Warnings acceptables uniquement

□  6. FEATURES EXISTANTES NON CASSÉES
     → Le chart se charge et affiche des bougies
     → L'order book se remplit
     → Le ticker footer défile
     → Le formulaire d'ordre fonctionne (paper trade)
     → JARVIS chat répond (si clé API configurée)
     → Le kill switch s'active/désactive

□  7. NOUVELLE FEATURE FONCTIONNE
     → Exécuter les critères de validation de l'étape (Section 2)
     → Chaque critère V.X.Y doit passer

□  8. MISE À JOUR PLAN.MD
     → Cocher les sous-tâches dans le tableau détaillé (Section 4.2)
     → Mettre à jour la carte de navigation (Section 1) si les lignes ont bougé
     → Marquer l'étape comme FAITE dans le suivi global (Section 4.1)

□  9. COMMIT & PUSH
     → git add server.py dashboard.html PLAN.md
     → git commit -m "feat: step XX — <description>"
     → git push -u origin claude/jarvis-trading-dashboard-HGW7A

□ 10. VÉRIFIER LE PUSH
     → Le commit apparaît sur GitHub
     → Le nombre de commits a augmenté de 1
```

---

### 5.2 PROTOCOLE DE TEST PAR TYPE DE MODIFICATION

#### A. Nouvelle route API (server.py)

```
1. python3 -m py_compile server.py
2. Démarrer le serveur
3. curl -s http://localhost:5000/api/<nouvelle-route> | python3 -m json.tool
   → Vérifier : code HTTP 200, JSON valide, champs attendus présents
4. curl avec paramètres invalides
   → Vérifier : code HTTP 400, message d'erreur descriptif
5. Ajouter la route dans scripts/health-check.sh
```

#### B. Nouvelle CSS (dashboard.html)

```
1. Ouvrir dans le navigateur, pas d'erreur visuelle
2. Vérifier que les nouvelles classes utilisent var(--xxx) pas de couleurs hardcodées
3. Tester en mode light (si étape 10.0 déjà faite) : les éléments restent lisibles
4. Tester en responsive (si étape 9.0 déjà faite) : pas de débordement à 375px
5. Vérifier les transitions (0.15s ease cohérent)
```

#### C. Nouveau JavaScript (dashboard.html)

```
1. Console DevTools : 0 erreurs au chargement
2. Console DevTools : 0 erreurs à l'interaction
3. Vérifier que toutes les fonctions utilisent "function" (pas de arrow functions)
4. Vérifier que les variables sont déclarées avec var/let/const (pas de globales implicites)
5. Tester le scénario nominal (golden path)
6. Tester le scénario d'erreur (réseau coupé, données vides)
7. Vérifier que le auto-refresh ne crée pas de fuites mémoire (pas d'accumulaton de listeners)
```

#### D. Nouvelle table SQLite (server.py)

```
1. Supprimer jarvis.db (ou le renommer)
2. python3 server.py → la table est créée automatiquement par init_db()
3. sqlite3 jarvis.db ".tables" → la nouvelle table apparaît
4. sqlite3 jarvis.db ".schema <table>" → le schéma correspond au plan
5. Tester INSERT, SELECT, DELETE via les routes API
```

#### E. Modification d'une fonction existante

```
1. Relire la fonction AVANT modification (dans PLAN.md section navigation)
2. S'assurer que le comportement existant est préservé
3. Tester le scénario existant (ne doit pas casser)
4. Tester le nouveau scénario ajouté
5. Si la fonction est appelée depuis startAutoRefresh(), vérifier qu'elle
   ne provoque pas de surcharge réseau
```

---

### 5.3 TESTS DE RÉGRESSION RAPIDES

Séquence de 60 secondes à exécuter après toute modification importante :

```
TEMPS  ACTION                                 VÉRIFIER
─────  ──────────────────────────────────────  ─────────────────────────
 0s    Ouvrir http://localhost:5000            Page se charge sans flash
 3s    Regarder le chart                      Bougies affichées
 5s    Regarder l'order book                  Asks et bids remplis
 8s    Regarder le ticker footer              Défilement actif
10s    Changer de symbole (cliquer ETH)       Chart, OB, ticker se mettent à jour
15s    Changer de timeframe (cliquer 4h)      Chart recharge
20s    Ouvrir JARVIS chat (cliquer AI)        Chat s'ouvre, pas d'erreur
25s    Cliquer un onglet Bottom Panel          Contenu change
30s    Ouvrir Settings (cliquer Settings)     Modal s'ouvre
35s    Fermer Settings (Escape)               Modal se ferme
40s    Ouvrir console DevTools                0 erreurs rouges
50s    Attendre 10 secondes                   Auto-refresh fonctionne (OB bouge)
60s    ✓ Régression OK
```

---

### 5.4 COMMANDES DE DIAGNOSTIC RAPIDE

```bash
# Vérifier syntaxe Python
python3 -m py_compile server.py && echo "OK" || echo "ERREUR"

# Compter les lignes (pour vérifier les insertions)
wc -l server.py dashboard.html

# Vérifier les routes déclarées
grep -c "@app.route" server.py

# Vérifier les fonctions JS
grep -c "^function \|^async function " dashboard.html

# Chercher les arrow functions (interdit)
grep -n "=>" dashboard.html | grep -v "<!--" | head -5

# Chercher les couleurs hardcodées (devrait utiliser var(--xxx))
grep -n "#[0-9a-fA-F]\{6\}" dashboard.html | grep -v ":root" | grep -v "data-theme" | grep -v "CHART_THEMES" | head -10

# Vérifier que les fichiers sensibles ne sont pas commités
git status --short | grep -E "\.env|secret\.key|jarvis\.db"

# Taille totale du projet
wc -l server.py dashboard.html PLAN.md
```

---

### 5.5 GESTION DES ERREURS COURANTES

| Erreur | Cause probable | Solution |
|--------|----------------|----------|
| `SyntaxError` dans server.py | Parenthèse manquante, indentation | `python3 -m py_compile server.py` pour localiser |
| Écran blanc dashboard | Erreur JS bloquante | Console DevTools → première erreur rouge |
| `TypeError: $(...) is null` | ID d'élément mal orthographié | Vérifier l'ID dans le HTML |
| Chart ne s'affiche pas | `lw-charts.js` non chargé | Vérifier que `<script src="lw-charts.js">` est avant le JS principal |
| Route retourne 404 | Route mal déclarée ou serveur pas redémarré | Redémarrer `python3 server.py` |
| CORS error dans console | Appel cross-origin | Vérifier que CORS est activé (déjà fait dans server.py) |
| SQLite "table locked" | Connexion non fermée | Vérifier `conn.close()` dans chaque route |
| Toast ne s'affiche pas | `showToast` appelé avant que le DOM soit prêt | Vérifier que l'appel est dans un handler, pas au top-level |
| Mémoire qui monte | setInterval sans cleanup | Vérifier que les timers sont dans `refreshTimers[]` |

---
