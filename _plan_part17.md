## 7. MISE À JOUR CLAUDE.MD & RÈGLES DE MAINTENANCE

---

### 7.1 CONTENU À AJOUTER DANS CLAUDE.MD

Ajouter la section suivante dans `CLAUDE.md` entre "## Testing" et "## Common Tasks" :

```markdown
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
```

Ajouter dans la section "## Common Tasks" :

```markdown
### Starting a new enhancement step
1. Read PLAN.md — find the next unchecked step in Section 4.1
2. Read the step's detail section (search "### ÉTAPE X.0")
3. Use text anchors (Section 6.2) to find insertion points — don't trust line numbers blindly
4. Follow the sub-tasks in order
5. Run the post-implementation checklist (Section 5.1)
6. Update PLAN.md: check sub-tasks, update navigation map, mark step as done
7. Commit with message: `feat: step XX — <description>`
```

Ajouter dans la section "## Do Not" :

```markdown
- Do not start coding an enhancement step without reading PLAN.md first
- Do not skip the post-implementation checklist after completing a step
- Do not trust PLAN.md line numbers after multiple steps — use text anchors
```

---

### 7.2 RÈGLES DE MISE À JOUR DE LA CARTE DE NAVIGATION

Après chaque étape, la carte de navigation (Section 1) doit être mise à jour
car les insertions de code décalent les numéros de ligne.

#### Procédure

```
1. Compter les lignes ajoutées dans chaque zone :
   - Lignes CSS ajoutées avant </style>
   - Lignes HTML ajoutées dans le body
   - Lignes JS ajoutées avant INIT ON DOM READY
   - Lignes ajoutées dans server.py

2. Recalculer les points d'insertion critiques :
   grep -n "</style>" dashboard.html
   grep -n "INIT ON DOM READY" dashboard.html
   grep -n '@app.route("/")' server.py

3. Mettre à jour Section 1.1 (ancres principales) avec les nouvelles valeurs

4. Mettre à jour les sections 1.2 → 1.7 :
   - Seules les zones APRÈS l'insertion bougent
   - Les zones AVANT l'insertion restent identiques
   - Décalage = nombre de lignes insérées
```

#### Exemple de mise à jour après l'étape 10.0 (Dark/Light Mode)

Supposons qu'on ajoute :
- 22 lignes CSS (variables light `[data-theme="light"]`)
- 1 ligne CSS (transition sur `*`)
- 2 lignes HTML (bouton dans navbar)
- 20 lignes JS (thème state + CHART_THEMES)
- 30 lignes JS (fonctions toggle/apply)

Alors :
```
dashboard.html AVANT : 3176 lignes
dashboard.html APRÈS : 3176 + 22 + 1 + 2 + 20 + 30 = 3251 lignes

Ancres mises à jour :
  </style>          : L:1175 → L:1198 (+23 lignes CSS)
  <!-- MAIN LAYOUT -->: L:1246 → L:1271 (+23 CSS + 2 HTML)
  INIT ON DOM READY : L:3142 → L:3189 (+23 CSS + 2 HTML + 20 JS avant init + 2 shift HTML)
```

#### Raccourci : utiliser les ancres textuelles

Au lieu de recalculer manuellement, toujours utiliser :

```bash
grep -n "</style>" dashboard.html
grep -n "INIT ON DOM READY" dashboard.html
grep -n "AUTO-REFRESH" dashboard.html
grep -n '@app.route("/")' server.py
```

Puis mettre à jour les valeurs dans la Section 1.1 du PLAN.md.

---

### 7.3 QUAND METTRE À JOUR QUOI

| Événement | PLAN.md à modifier | CLAUDE.md |
|-----------|--------------------|-----------| 
| Étape terminée | Section 4.1 (suivi), Section 4.2 (sous-tâches), Section 1.1 (ancres) | Non |
| Nouvelle route API ajoutée | Section 1.6 (routes) | Non |
| Nouvelle fonction JS ajoutée | Section 1.4 (JS) | Non |
| Nouvelle classe Python ajoutée | Section 1.5 (structure) | Ajouter dans "Important Classes" |
| Nouvelle table SQLite | Section 1.5 | Non |
| Nouveau script shell | Non | Ajouter dans "Testing" |
| Toutes les 10 étapes terminées | Archiver, créer PLAN_v2.md | Mettre à jour les compteurs de lignes |

---

### 7.4 FORMAT DU COMMIT DE MISE À JOUR PLAN.MD

La mise à jour du PLAN.md se fait dans LE MÊME commit que l'étape :

```
git add server.py dashboard.html PLAN.md
git commit -m "feat: step XX — <description>"
```

Ne PAS faire un commit séparé pour la mise à jour du PLAN.md.
Le PLAN.md est un outil vivant, pas un livrable — il évolue avec le code.

---
