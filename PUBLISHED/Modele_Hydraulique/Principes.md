# Calibration
Le modèle hydraulique est calibré sur la base des mesures réalisées au niveau des **exutoires**, dans les **galeries** (Sondierstollen ou Fensterstollen) et dans le **réseau karstique**. 
Il s'agit essentiellement des mesures suivantes:
- Mesures de **débits**:
    - Source de la Brunnmühle°
    - Entwaesserungstollen°
    - Fensterstollen°
- Mesures de **hauteurs d'eau**:
    - Wasserhooliloch°
    - Gischeren 
    - Schüttstein
    - Venues d'eau dans le Sondierstollen°: SS1, SS3, SS4 et SS5
Les stations marquées d'un (°) sont suivies en continue. Les autres stations ont fait l'objet d'un suivi plus court, la plupart du temps sur quelques mois. 
Certains débits ont pu être reconstitués pour aider à la calibration: 
- Les débits de **débordement** du Wasserhooliloch
- Les débits de la source de la Sauser, en bordure de la vasque du Twannbach
Le modèle est calibré avec une chronique de débits factice en input; il s'agit d'une succession d'évènements de crues entrecoupés de période sans recharge. 
La calibration est opérée selon deux controles: 
- La reproductibilité des **débits aux exutoires** et des **fluctuations de hauteurs d'eau** dans le réseau de conduits
- la reproductibilité des **relations hydrauliques** entre les exutoires. Ces relations permettent de vérifier que les réponses hydrauliques simulées entre différents points du réeau de conduits sont conformes à celle mesurées. Elles sont de 3 types:
    - Q vs. Q (Débit exutoire A vs. débit exutoire B)
    - Q vs. H (Débit exutoire A vs. hauteur d'eau point C du réseau de conduits)
    - H vs. H (Hauteur d'eau point C du réseau de conduits vs. hauteur d'eau point D du réseau de conduits)

> [!NOTE] 
> Comme convenu avec le MO/BAMO, les régimes de références pour la calibration sont ceux mesurés depuis 2023, en raison des modifications du régime hydrologique apportées par les travaux de la nouvelle station de pompage de la Brunnmühle. 

## Inputs
Une **chronique de débits** en input du modèle hydraulique a été reconstituée, sur la base des mesures disponibles entre 2016 et 2026, au pas de temps horaire, à savoir:
- Les débits de la source de la Brunnmühle 
- Les débits de l'Entwaesserungstollen
- Les débits du Twannbach aval
- Les débits du Twannbach amont

La règle de reconstitution de la chronique de débits en input du modèle hyraulique est la suivante:
>Q<small>input</small> = [Q_Brunnmühle + Q_Entwaesserungstollen + Q_Twannbach_Unten] - Q_Twannbach_Oben

La règle s'applique sur l'ensemble de la chronique **sauf** si:
- **Q_Twannbach_Oben > Q_Twannbach_Unten** (ce qui en théorie n'est pas possible, mais étant donné que la courbe de conversion des débits de la station Twannbach_Oben est relativement incertaine en trés hautes eaux),
- Une station au moins ne présente pas de mesures sur la période considérée. 
Le graphique suivant présente la chronique de débits reconstituée entre 2016 et 2026.

<iframe
    src="/Twanntunnel_Hydraulic_SWMM/Discharge_Input_SWMM_plot.html"
    width="100%"
    height="800px"
></iframe>

La liste suivante pointe les périodes de lacunes pour chaque station présentant des lacunes de mesures. 
- Brunnmuehle_Quelle: 7
    - 2018-11-15 09:00 -> 2019-05-11 23:00 (4263 h)
    - 2020-09-13 01:00 -> 2020-09-25 23:00 (311 h)
    - 2021-10-07 01:00 -> 2021-10-31 23:00 (599 h)
    - 2021-11-08 01:00 -> 2022-03-10 23:00 (2951 h)
    - 2022-07-29 01:00 -> 2022-08-19 23:00 (527 h)
    - 2022-08-21 01:00 -> 2022-09-05 23:00 (383 h)
    - 2023-09-29 01:00 -> 2023-10-20 23:00 (527 h)
- Entwaesserungstollen: 8
    - 2019-01-01 00:00 -> 2019-02-20 23:00 (1224 h)
    - 2020-09-13 10:00 -> 2020-09-26 09:00 (312 h)
    - 2021-11-20 04:00 -> 2022-02-24 23:00 (2324 h)
    - 2022-07-29 08:00 -> 2022-08-20 16:00 (537 h)
    - 2022-08-22 00:00 -> 2022-09-05 23:00 (360 h)
    - 2023-09-29 12:00 -> 2023-10-09 21:00 (250 h)
    - 2023-10-11 03:00 -> 2023-10-21 08:00 (246 h)
    - 2023-10-22 12:00 -> 2023-10-24 12:00 (49 h)
- Twannbach_Unten: 3
    - 2019-04-01 15:00 -> 2019-04-05 06:00 (88 h)
    - 2019-04-26 05:00 -> 2019-06-26 15:00 (1475 h)
    - 2022-12-21 06:00 -> 2023-01-31 14:00 (993 h)
- Twannbach_Oben: 7
    - 2020-02-18 12:00 -> 2020-07-16 11:00 (3576 h)
    - 2020-09-17 18:00 -> 2020-09-25 12:00 (187 h)
    - 2020-10-22 18:00 -> 2020-10-26 23:00 (102 h)
    - 2020-12-02 16:00 -> 2020-12-24 15:00 (528 h)
    - 2021-02-26 10:00 -> 2021-03-01 06:00 (69 h)
    - 2021-03-27 17:00 -> 2021-03-31 09:00 (89 h)
    - 2021-03-31 14:00 -> 2021-04-23 06:00 (545 h)

La courbe des débits classés est basée sur l'analyse de 45820 valeurs horaires. Elle est affichée ci-dessous. 
>Qmax = 18.79 m<sup>3</sup>/s
>Qmedian = 0.73 m<sup>3</sup>/s

<iframe src="/Twanntunnel_Hydraulic_SWMM/Discharge_Input_SWMM_flow_duration_curve.html"

    width="100%"
    height="800px"
    frameBorder="0"
></iframe>

## Débits aux exutoires
En conditions de hautes eaux, la calibration peut être partiellement réalisée sur les mesures de débits du **Fensterstollen** (pas de temps horaire), sachant qu'en conditions de hautes eaux, les débits sont plafonnés par (i) les venues d'eau dans la galerie et (ii) la section de la trappe, et sur les débits reconstitués du **Wasserhooliloch** (pas de temps horaire) - sachant qu'il existe une certaine incertitude sur ces valeurs.  
### Brunnmühle (source)
Les débits de la source de la Brunnmühle sont indirectement mesurés depuis 2013. Ils sont obtenus en soustrayant les débits de l'Entwässerungstollen aux débits du Quellteich. 
> [!IMPORTANT]  
> Les débits de la source de la Brunnmühle ont été "perturbés" depuis l'aménagement et la mise en service de la nouvelle station de pompage de Brunnmühle en 2023. Ces contraintes ont pour conséquence de réduire la période de calibration du modèle hydraulique sur la période post-2023.
### Fensterstollen
Le tableau suivant indique les débits mesurés et extrapolés à la station Fensterstollen pour des temps de retour de  2 ans, 3 ans, 5 ans, 10 ans, 30 ans et 100 ans. Pour les temps de retour **=< 10 ans**, les valeurs sont issues des mesures. Pour les temps de retour **> 10 ans**, elles sont extrapolées.

Le tableau indique aussi les dates des évènements observés en fonction de leur temps de retour. 

| Temps de retour (années) | Débit Fensterstollen (m3/s) | Dates évènements                                                                                    |
| ------------------------ | --------------------------- | --------------------------------------------------------------------------------------------------- |
| T2                       | 1.5                         |                                                                                                     |
| T3                       | 1.6                         |                                                                                                     |
| T5                       | 1.75                        | 23/06/2021<br />26/12/2021<br />15/03/2023                                                              |
| T10                      | 1.9                         | 16.07.2021 (2.015 m3/s)<br />30/12/2021 (1.9 m3/s)<br />15/03/2023 (2.01 m3/s)<br />03/04/2023 (1.9 m3/s) |
| T30                      | 2.1                         | Pas d’évènement                                                                                     |
| T100                     | 2.4                         | Pas d’évènement                                                                                     |
| T300                     | 2.67                        | Pas d’évènement                                                                                     |

> [!IMPORTANT]  
> Les débits >T30 doivent être considérés avec la plus grande prudence. 
### Wasserhooliloch
Les débits de débordement du Wasserhooliloch ne sont pas mesurés. Ils peuvent être reconstruits au pas de temps horaire selon la règle suivante:

> Q_Wasserhooliloch = Q_Twannbach_unten - (Q_Twannbach_Oben + Q_Fensterstollen)

> [!NOTE] 
> Q_Wasserhooliloch n'est pas calculé si Q_Twannbach_unten < (Q_Twannbach_Oben + Q_Fensterstollen).
> 
> Idem, si au moins une des stations présente une lacune de mesures > 48 h, le calcul n'est pas réalisé.

Le tableau suivant présente les débits de débordement mesurés et/ou extrapolés pour la station **Wasserhooliloch**, ainsi que l'intervalle de confiance IC95 et les dates supposées des évènements si ils ont été mesurés. 

| Temps de retour | Q (m3/s) | IC95 (m3/s) | Dates évènements                                                |
|-----------------|----------|-------------|-----------------------------------------------------------------|
| T1              | 9.0      |             | 2022-10-24 19:00<br />2025-10-30 08:00<br />2024-09-27 01:00<br />... |
| T2              | 12.6     | 10.9 - 14.1 | 2021-07-15 21:00<br />2025-01-09 03:00<br />2024-01-18 23:00<br />... |
| T3              | 13.5     | 12 - 14.7   | 2024-10-02 07:00<br />2018-12-22 04:00<br />2023-12-11 17:00<br />... |
| T5              | 14.5     | 13 - 15.6   | 2023-12-12 13:00<br />2023-11-14 09:00<br />2024-10-02 06:00        |
| T10             | 15.7     | 13.6 - 17.1 | 2023-12-13 03:00<br />2023-11-14 09:00<br />2024-10-02 06:00        |
| T30             | 17.5     | 13.9 - 19.4 | 2023-12-13 05:00 (?)                                            |
| T100            | 19.5     | 14.3 - 21.9 | 2023-12-13 05:00 (?)                                            |
| T300            | 21.3     | 14.7 - 24.4 | Aucun évènement                                                 |

> [!IMPORTANT]  
> Les débits de temps de retour >T30 sont très extrapolés par rapport à la période observée. 
### Sauserquelle
Les débits de la source Sauserquelle ne sont pas mesurés. Ils sont **reconstitués** sur la base de la relation suivante: 

> Q_Sauser = Q_Twannbach_unten - (Q_Fensterstollen)

> [!NOTE]  
> Q_Sauser n'est pas calculé si Q_Twannbach_Oben > 0.
## Hauteurs d'eau
### Wasserhooliloch
Les hauteurs d'eau sont mesurées au fond de la partie humainement atteignable du gouffre.
Les mesures sont disponibles depuis 2014.
### Gischeren
Les hauteurs d'eau dans la grotte de **Gischeren** ont fait l'objet de mesures en continu entre 2015 et 2017. La chronique totalise seulement 2 années de mesures. 
### Schüttstein
Les hauteurs d'eau dans la grotte de **Schüttstein** ont fait l'objet de mesures en continu entre 2015 et 2017. La chronique totalise seulement 2 années de mesures. 
### Sondierstollen (SS1 à SS6)
les principales venues d'eau dans le Sondierstollen (**SS1**, **SS3**, **SS4** et **SS5**) ont fait l'objet de mesures entre 2015 et 2017. Les mesures indiquent principalement le **"seuil d'activation"** et les **périodes d'activité** de chaque venue d'eau ou groupes de venues d'eau. 
Les mesures restent qualitatives, elles n'informent pas sur les débits. 
## Relations hydrauliques
La calibration du modèle hydraulique repose sur les relations hydrauliques observés entre les différentes stations de mesures. Elles sont de 3 types:
- Hauteurs d'eau station(x) vs. Hauteurs d'eau station(y)
- Débits station(x) vs. Débits station(y)
- Hauteurs d'eau station(x) vs. Débits station(y)
Les relations principales relations hydrauliques ont été analysés dans les rapports 2014, 2015, 2016 et 2017. L'article [Jeannin et al. 2016](https://link.springer.com/article/10.1007/s12665-015-4655-5) présente une synthèse de ces calibrations. 
