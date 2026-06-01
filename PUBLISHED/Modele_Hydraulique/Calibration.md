# Calibration du modèle hydraulique

Le modèle hydraulique est calibré sur la base des mesures réalisées au niveau des exutoires, dans les galeries (Sondierstollen ou Fensterstollen) et dans le réseau karstique. 

Il s'agit essentiellement des mesures suivantes:
- Mesures de débits:
    - Source de la Brunnmühle*
    - Entwaesserungstollen*
    - Fensterstollen*
- Mesures de hauteurs d'eau:
    - Wasserhooliloch*
    - Gischeren 
    - Schüttstein
    - Venues d'eau dans le Sondierstollen: SS3, SS4, SS5 et SS6

Les stations marquées d'un (*) sont suivies en continue. Les autres stations ont fait l'objet d'un suivi plus court, la plupart du temps sur quelques mois. 

Le modèle est calibré avec une chronique de débits factice en input; il s'agit d'une succession d'évènements de crues entrecoupés de période sans recharge. 

La calibration est opérée selon deux controles: 
- La reproductibilité des **débits aux exutoires** et des **fluctuations de hauteurs d'eau** dans le réseau de conduits
- la reproductibilité des **relations hydrauliques** entre les exutoires. Ces relations permettent de vérifier que les réponses hydrauliques simulées entre différents points du réeau de conduits sont conformes à celle mesurées. Elles sont de 3 types:
    - Q vs. Q (Débit exutoire A vs. débit exutoire B)
    - Q vs. H (Débit exutoire A vs. hauteur d'eau point C du réseau de conduits)
    - H vs. H (Hauteur d'eau point C du réseau de conduits vs. hauteur d'eau point D du réseau de conduits)

## Débits aux exutoires

En conditions de hautes eaux, la calibration peut être partiellement réalisée sur les mesures de débits du **Fensterstollen** (pas de temps horaire), sachant qu'en conditions de hautes eaux, les débits sont plafonnés par (i) les venues d'eau dans la galerie et (ii) la section de la trappe, et sur les débits reconstitués du **Wasserhooliloch** (pas de temps horaire) - sachant qu'il existe une certaine incertitude sur ces valeurs.  

### Fensterstollen

Le tableau suivant indique les débits mesurés et extrapolés à la station Fensterstollen pour des temps de retour de  2 ans, 3 ans, 5 ans, 10 ans, 30 ans et 100 ans. Pour les temps de retour **=< 10 ans**, les valeurs sont issues des mesures. Pour les temps de retour **> 10 ans**, elles sont extrapolées.

Le tableau indique aussi les dates des évènements observés en fonction de leur temps de retour. 

| Temps de retour (années) | Débit Fensterstollen (m3/s) | Dates évènements                                                                                    |
|--------------------------|-----------------------------|-----------------------------------------------------------------------------------------------------|
| T2                       | 1.5                         |                                                                                                     |
| T3                       | 1.6                         |                                                                                                     |
| T5                       | 1.75                        | 23/06/2021<br>26/12/2021<br>15/03/2023                                                              |
| T10                      | 1.9                         | 16.07.2021 (2.015 m3/s)<br>30/12/2021 (1.9 m3/s)<br>15/03/2023 (2.01 m3/s)<br>03/04/2023 (1.9 m3/s) |
| T30                      | 2.1                         | Pas d’évènement                                                                                     |
| T100                     | 2.4                         | Pas d’évènement                                                                                     |


### Wasserhooliloch

Les débits de débordement du Wasserhooliloch ne sont pas mesurés. Ils peuvent être reconstruits au pas de temps horaire selon la règle suivante:

> Q_Wasserhooliloch = Q_Twannbach_unten - (Q_Twannbach_Oben + Q_Fensterstollen)

> [!NOTE]  
> - Q_Wasserhooliloch n'est pas calculé si Q_Twannbach_unten < (Q_Twannbach_Oben + Q_Fensterstollen).
- Idem, si au moins une des stations présente une lacune de mesures > 48 h, le calcul n'est pas réalisé.

Le tableau suivant présente les débits de débordement mesurés et/ou extrapolés pour la station **Wasserhooliloch**, ainsi que l'intervalle de confiance IC95 et les dates supposées des évènements si ils ont été mesurés. 

| Temps de retour | Q (m3/s) | IC95 (m3/s) | Dates évènements                                                |
|-----------------|----------|-------------|-----------------------------------------------------------------|
| T1              | 9.0      |             | 2022-10-24 19:00<br>2025-10-30 08:00<br>2024-09-27 01:00<br>... |
| T2              | 12.6     | 10.9 - 14.1 | 2021-07-15 21:00<br>2025-01-09 03:00<br>2024-01-18 23:00<br>... |
| T3              | 13.5     | 12 - 14.7   | 2024-10-02 07:00<br>2018-12-22 04:00<br>2023-12-11 17:00<br>... |
| T5              | 14.5     | 13 - 15.6   | 2023-12-12 13:00<br>2023-11-14 09:00<br>2024-10-02 06:00        |
| T10             | 15.7     | 13.6 - 17.1 | 2023-12-13 03:00<br>2023-11-14 09:00<br>2024-10-02 06:00        |
| T30             | 17.5     | 13.9 - 19.4 | 2023-12-13 05:00 (?)                                            |
| T100            | 19.5     | 14.3 - 21.9 | 2023-12-13 05:00 (?)                                            |


## Relations hydrauliques


iframe relations hydrauliques ?
