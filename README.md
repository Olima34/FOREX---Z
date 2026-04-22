# FOREX-Z - V2 Agentic AI Manual

Manual operationnel pour agents IA qui doivent modifier, tester ou etendre le projet vite, avec un minimum de lecture de code.

## 1) Mission Systeme

FOREX-Z calcule un score macro par paire Forex en combinant:

1. surprise economique par pays
2. normalisation statistique (z-score)
3. composante sentiment COT
4. agregation finale par paire

Objectif agent:

- produire des changements sans casser les invariants de pipeline
- garder les cycles idempotents
- maintenir la coherence SQLite et tests

## 2) Ou Commencer (Chemin court agent)

Lire dans cet ordre:

1. `main.py`
2. `config.py`
3. `utils/parametres.py`
4. `economic_data/scripts/country_indicator.py`
5. `maths_stats/z_score_calculation.py`
6. `economic_data/scripts/pair_indicator_score.py`
7. `economic_data/scripts/pair_total_score.py`
8. `sentiment/scripts/cot.py`
9. `utils/gestion_db.py`

Puis valider via tests:

- `tests/unit/`
- `tests/http/`
- `tests/integration/`

## 3) Graphe D Execution (Cycle Runtime)

Ordre orchestre par `main.py`:

1. country indicators
2. cot sentiment
3. carry
4. pair indicator scores
5. pair total scores

Contrat global:

- chaque etape retourne un entier (nb de lignes mises a jour)
- les erreurs doivent etre loguees et ne pas stopper completement la boucle

Cadence:

- boucle toutes les 3600s
- retry apres crash non fatal: 300s

## 4) Contrats De Donnees (Tables)

### `country_indicators`

Owner ecriture: `country_indicator.update_due()`

Usage:

- source brute pour z-scores, carry, pair-indicator-score
- historique append-only

Colonnes pivots:

- `country`, `indicator`, `actual`, `consensus`, `forecast`, `previous`
- `date_release`, `next_update_ts`, `timestamp`

### `z_scores`

Owner ecriture: `update_z_scores()` (upsert)

Usage:

- fournit `get_z_score_factor(country, indicator)` pour pondere les scores

Colonnes pivots:

- PK `(country, indicator)`
- `z_score`, `historical_mean`, `historical_std`, `historical_count`
- `calculation_timestamp`

### `cot_sentiment`

Owner ecriture: `cot.update()`

Usage:

- composante sentiment dans score final

Colonnes pivots:

- `pair`, `pair_sentiment`, `timestamp`

### `carry_trade`

Owner ecriture: `carry.update_due()`

Usage:

- sortie intermediaire de differenciel de taux

Colonnes pivots:

- `pair`, `carry_value`
- `base_interest_rate_id`, `quote_interest_rate_id`

### `pair_indicator_scores`

Owner ecriture: `pair_indicator_score.update_due()`

Usage:

- entree principale de `pair_total_score`

Colonnes pivots:

- `pair`, `indicator`, `pair_score`
- `base_indicator_id`, `quote_indicator_id`
- `base_z_factor`, `quote_z_factor`, `calculation_timestamp`

### `pair_total_scores`

Owner ecriture: `pair_total_score.update_due()`

Usage:

- sortie finale exploitable par strategie / affichage / downstream

Colonnes pivots:

- `pair`, `total_score`
- `indicator_scores_json`, `indicator_ids_json`

## 5) Contrats Fonctionnels Critiques

### country_indicator

- `fetch(country, indicator, reference) -> dict|None`
  - doit retourner structure complete meme si certaines valeurs sont `None`
  - ne doit pas lever en erreur reseau/parsing (retourne `None` + logs)
- `data_changed(latest, result) -> bool`
  - ne doit pas remplacer une ligne valide par une ligne totalement vide
- `update_due() -> int`
  - si au moins une ligne change, doit declencher `update_z_scores()`

### z_score_calculation

- `update_z_scores() -> bool`
  - exige au moins 3 surprises valides
  - ignore series sans variance (`std == 0`)
- `get_z_score_factor(...) -> float`
  - fallback neutre obligatoire: `1.0`

### pair_indicator_score

- `calculate_indicator_score(...) -> float`
  - logique reference: consensus sinon forecast
  - inversion obligatoire pour `BAD_INDICATORS`
- `get_due()`
  - doit detecter changement donnees ET changement z-factors

### pair_total_score

- `get_cot_sentiment_score(pair) -> float`
  - applique ponderation exponentielle
- `scores_changed(pair, last_scores) -> bool`
  - compare flottants avec tolerance `0.0001`

### cot

- `should_update_cot() -> bool`
  - gouverne la frequence d ingestion COT
- `update() -> int`
  - doit ecrire une ligne par paire COT mappable

## 6) Formules Canoniques (A respecter)

Surprise:

$$
surprise = actual - (consensus \text{ sinon } forecast)
$$

Factor z-score:

$$
factor = 1 + |z| \times coefficient_{indicator}
$$

Score indicateur pays:

$$
score =\begin{cases}
1 & actual > reference\\
-1 & actual < reference\\
0 & actual = reference
\end{cases}
$$

Puis inversion si indicateur defavorable (ex: unemployment-rate), puis multiplication par `factor`.

Score paire indicateur:

$$
pair\_score = base\_score - quote\_score
$$

Score COT pondere:

$$
cot\_weight = e^{|sentiment| \cdot COT\_EXPONENTIAL\_FACTOR}
$$

$$
cot\_influence = sentiment \cdot cot\_weight
$$

Score total:

$$
total\_score = \sum pair\_score_{indicators} + cot\_influence
$$

## 7) Regles Due/Idempotence (Checklist Agent)

Avant de modifier une logique `update_due()` verifier:

1. condition de due basee sur derniere valeur en DB
2. pas de reecriture inutile si rien n a change
3. resultat stable si on rejoue 2 fois de suite
4. logs explicites `OK` vs `SKIP`

## 8) Sources Externes (Risques + Garde-fous)

Trading Economics:

- parsing HTML via pandas
- risque: structure de page change
- garde-fou: exceptions capturees, `None` retourne

CFTC COT:

- parsing CSV avec schema `COT_COLUMNS`
- filtrage strict sur `COT_NAMES`
- risque: publication/horodatage, fuseau local

## 9) Runbooks Agentiques

### A) Je vois des scores a 0 partout

1. verifier `country_indicators.actual/consensus/forecast`
2. verifier presence de donnees pour les 2 pays de la paire
3. verifier z-factor (doit etre >= 1.0)
4. verifier `BAD_INDICATORS` (inversion)

### B) COT ne se met pas a jour

1. verifier `should_update_cot()`
2. verifier `cot_sentiment` latest timestamp
3. forcer temporairement via monkeypatch en test integration

### C) Pair total ne bouge pas

1. verifier `pair_indicator_scores` latest par indicateur
2. verifier `scores_changed(...)`
3. verifier presence sentiment COT pour la paire

## 10) Recettes De Changement Frequent

### Ajouter un indicateur macro

1. ajouter dans `config.py` -> `INDICATORS`
2. renseigner reference Trading Economics par pays dans `COUNTRIES`
3. definir coefficient dans `utils/parametres.py`
4. si indicateur inverse, l ajouter a `BAD_INDICATORS`
5. ajouter tests unit + integration

### Ajouter une paire

1. ajouter mapping dans `PAIRS`
2. ajouter mapping COT dans `COT_PAIRS` si necessaire
3. verifier que les 2 pays ont les 7 indicateurs requis

### Modifier la ponderation sentiment

1. ajuster `COT_EXPONENTIAL_FACTOR`
2. revalider tests `test_cot_sentiment_score_weighted_exponentially`
3. observer impact distribution `pair_total_scores`

## 11) Verifications Avant Merge (Gate Agent)

Executer:

```bash
pytest
ruff check .
mypy .
```

Puis controler rapidement:

1. aucun changement non voulu dans schema SQL
2. aucune regression sur idempotence
3. logs toujours actionnables (contexte + paire + indicateur)

## 12) Commandes Utiles

Installer runtime:

```bash
pip install -r requirements.txt
```

Installer dev:

```bash
pip install -r requirements-dev.txt
```

Init DB:

```bash
python database/init_db.py
```

Run boucle:

```bash
python main.py
```

## 13) Limitations Connues

- `database/migrate_to_sqlite.py` est legacy et hors flux principal
- pas de versionning de migration DB centralise
- configuration metier essentiellement hard-codee dans `config.py`
- sensibilite du timing COT a l horloge/fuseau local

## 14) Resume Ultra Court Pour Agent

Si tu dois agir en 60 secondes:

1. lis `config.py` et `utils/parametres.py` (regles metier)
2. lis `main.py` (ordre runtime)
3. lis `country_indicator.py`, `pair_indicator_score.py`, `pair_total_score.py` (coeur scoring)
4. valide via `pytest`
5. si bug de donnees, inspecte d abord SQLite avant de toucher les formules
