"""
Fichier de paramètres centralisé pour le système de scoring FOREX.

Source unique de vérité pour tous les coefficients et seuils. Le module
`config.py` ré-exporte `INDICATOR_COEFFICIENTS` pour compatibilité.
"""

# Facteur exponentiel pour le calcul du poids COT.
# Ancienne valeur : 0.001 (trop faible, la composante sentiment ne pesait
# quasiment rien dans le score final). 0.1 met le sentiment dans la même
# ordre de grandeur que les scores économiques (cf. audit / README).
COT_EXPONENTIAL_FACTOR: float = 0.1

# Coefficients de pondération pour chaque indicateur macro.
# Somme ≈ 1.0 — représente l'importance relative de chaque indicateur.
INDICATOR_COEFFICIENTS: dict[str, float] = {
    "gdp-growth": 0.173,
    "interest-rate": 0.192,
    "unemployment-rate": 0.135,
    "inflation-cpi": 0.154,
    "balance-of-trade": 0.115,
    "current-account": 0.096,
    "retail-sales": 0.135,
}

# Coefficient par défaut si un indicateur inconnu est rencontré.
DEFAULT_INDICATOR_COEFFICIENT: float = 0.15

# Timeout (secondes) appliqué à toutes les requêtes HTTP sortantes.
HTTP_TIMEOUT: int = 30

# Durée entre deux cycles de la boucle principale (secondes).
MAIN_LOOP_INTERVAL_SECONDS: int = 3600

# Durée d'attente après un crash non fatal dans la boucle principale.
MAIN_LOOP_ERROR_BACKOFF_SECONDS: int = 300
