# Simulations hydrauliques

## Inputs

Une chronique de débits en input du modèle hyraulique a été reconstituée, sur la base des mesures disponibles entre 2016 et 2026, au pas de temps horaire, à savoir:
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

frame

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



## Débits projets

Les **débits projets** considérés pour les simulations sont les suivants: T0.5, T1, T2, T3, T5, T10, T30 et T100 ans.
- Les débits T0.5, T1, T2, T3, T5 et T10 sont évalués sur la base des mesures.
- Les débits T30 et T100 sont extrapolés selon deux variantes:
    - Une variante "**prudente**", sur base logarithmique ("**log**"): 
        > Q = a + b ln(T).
    
        Elle représente plutôt une estimation prudente pour les grands temps de retour.

    - Une variante plus "**extrême**", sur base exponentielle ("**exp**") : 
        > Q = exp(a) * T^b. 

        Cette variante permet une croissance plus rapide des débits.

Le tableau ci-dessous présente les valeurs de débits considérés pour les temps de retour listés plus haut.

| T   | Statut          | Gumbel | Log (prudente) | Exp (extrême) |
|-----|-----------------|--------|----------------|---------------|
| 0.5 | Approximé       | n/a    | 7.528          | 8.602         |
| 1   | limite / mesuré | n/a    | 10.208         | 10.405        |
| 2   | mesuré          | 13.254 | 12.889         | 12.585        |
| 3   | mesuré          | 14.713 | 14.456         | 14.066        |
| 5   | mesuré          | 16.338 | 16.432         | 16.183        |
| 10  | mesuré          | 18.380 | 19.112         | 19.574        |
| 30  | extrapolé       | 21.465 | 23.360         | 26.463        |
| 100 | extrapolé       | 24.773 | 28.015         | 36.826        |

> [!NOTE]  
> - la valeur **T0.5** est peu standard dans l'approche de type Gumbel, elle est donc approximée.
  - Les valeurs **T30** et **T100** sont toutes deux extrapolées!



## Contrôles