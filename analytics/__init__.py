"""
Module d'analyse backtest : mesure le pouvoir prédictif des scores macro
FOREX-Z en les corrélant aux rendements forex observés.

L'idée est simple : si les scores du pipeline ont une valeur, alors un
score élevé à la date `t` doit, en moyenne, être suivi d'un rendement
positif sur la paire à la date `t + horizon`. On quantifie cela par :

- l'IC (information coefficient, Spearman) entre scores et rendements ;
- le hit rate (signe du score vs signe du rendement) ;
- la perf cumulée / Sharpe d'une stratégie simple long/short pilotée
  par le signe du score ;
- le drawdown max.
"""
