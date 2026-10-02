# Simulations

Cette page décrit le workflow utilisé pour lancer les simulations hydrauliques de masse du modèle SWMM Twannbach et pour exploiter les résultats par scénario, temps de retour, phase et probabilité.

## Principe général

Les simulations sont pilotées par le script:

```powershell
D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\MASS_COMPUTATION\run_swmm_mass_computation.py
```

Le script part du modèle de base:

```powershell
D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\SWMM_Twannbach.inp
```

Il lit ensuite le fichier de scénarios:

```powershell
D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\MASS_COMPUTATION\scenarios.txt
```

Pour chaque combinaison de variantes retenue, le script génère un fichier `.inp`, lance SWMM, lit les résultats et inscrit une ligne dans un fichier `.csv`.

Les simulations couvrent actuellement une période de 24 h, entre le 01.01.2000 et le 02.01.2000, au pas de temps horaire. Les débits extraits des fichiers `.out` correspondent donc à des valeurs stabilisées au pas horaire et non aux pics instantanés du rapport `.rpt`.

## Scénarios et variantes

Le fichier `scenarios.txt` décrit les scénarios selon une logique hiérarchique:

- `scenario`: nom du scénario simulé, par exemple `scenario1`.
- `phase`: phase ou sous-phase constructive, par exemple `1_1a`, `1_2b`, `1_7a`.
- `variant`: variante possible dans une phase donnée.
- `prob=...`: probabilité associée à une variante active.
- `constant_flow`: situation hydrologique simulée.

Les variantes sont cumulatives entre phases. Une simulation de la phase `1_3a` peut donc reprendre des variantes sélectionnées en `1_1a`, `1_1b`, `1_2a` et `1_2b`.

Lorsque `combine_variants_within_phase yes` est actif, les variantes d'une même phase peuvent aussi être combinées entre elles. Par exemple, pour une phase avec trois variantes actives `V1`, `V2`, `V3`, les combinaisons testées incluent `V1`, `V2`, `V3`, `V1+V2`, `V1+V3`, `V2+V3` et `V1+V2+V3`.

Les variantes de type `_0` représentent le cas "sans modification". Elles ne sont pas combinées avec les variantes actives, car `V0+V1` est équivalent à `V1`.

## Actions disponibles

Les actions décrites dans `scenarios.txt` modifient temporairement le fichier SWMM de base pour générer un `.inp` propre à chaque simulation. Les actions utilisées comprennent notamment:

- ajout de conduits entre deux noeuds;
- modification du diamètre ou de la géométrie d'un conduit;
- modification de l'altitude d'une junction;
- modification de l'altitude d'un outfall;
- ajout de conditions de débit constant.

Les actions placées directement sous une `phase` sont communes à toutes les variantes de cette phase. Les actions placées sous une `variant` ne s'appliquent qu'aux combinaisons qui incluent cette variante.

## Temps de retour simulés

Les temps de retour sont actuellement représentés par un débit constant imposé en entrée amont:

| Temps de retour | Débit amont |
| --- | ---: |
| T3 | 14.7 m3/s |
| T10 | 18.4 m3/s |
| T30 | 21.5 m3/s |
| T50 | 22.9 m3/s |

Le débit principal est injecté sur `Amont_C` via la timeseries `Real_disch_as_input`.

Un apport secondaire est aussi appliqué sur le conduit `48`, via la timeseries `Real_disch_as_input_conduit_48`. Sa valeur est définie dans le script par `SECONDARY_INPUT_FRACTION`.

Pour changer le temps de retour à simuler, il faut décommenter une seule ligne `constant_flow` dans `scenarios.txt`, par exemple:

```txt
constant_flow T3 14.7
# constant_flow T10 18.4
# constant_flow T30 21.5
# constant_flow T50 22.9
```

## Probabilités

Chaque variante active peut recevoir une probabilité avec la syntaxe:

```txt
prob=0.15
```

La probabilité d'une combinaison est calculée en multipliant les probabilités des variantes actives qui la composent.

Pour les variantes `_0`, la probabilité est déduite comme la probabilité résiduelle de la phase, c'est-à-dire:

```txt
P(V0) = 1 - somme(P(variantes actives de la phase))
```

Les combinaisons dont la probabilité est inférieure ou égale au seuil défini par `MIN_COMBINATION_PROBABILITY` ne sont pas reprises dans les phases suivantes. Le seuil utilisé actuellement est:

```python
MIN_COMBINATION_PROBABILITY = 1e-4
```

Ce filtrage limite l'explosion combinatoire tout en conservant les combinaisons les plus probables.

## Lancement des simulations

Depuis Anaconda PowerShell:

```powershell
cd D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM
C:\Users\ISSKA\anaconda3\envs\spyder\python.exe MASS_COMPUTATION\run_swmm_mass_computation.py --workers 6
```

Depuis Spyder, utiliser la syntaxe:

```python
%runfile D:/Users/ISSKA/Documents/GitHub/Twanntunnel_Hydraulic_SWMM/MASS_COMPUTATION/run_swmm_mass_computation.py --wdir D:/Users/ISSKA/Documents/GitHub/Twanntunnel_Hydraulic_SWMM --args "--workers 6"
```

L'option `--workers 6` permet de lancer plusieurs simulations SWMM en parallèle. La valeur peut être adaptée en fonction du nombre de coeurs disponibles et de la charge acceptable sur la machine.

> [!IMPORTANT]
> Ne pas utiliser `--use-rpt-only` pour les graphes finaux de débits. Cette option lit les maxima instantanés du rapport `.rpt`, qui peuvent contenir des artefacts numériques. Les valeurs stabilisées doivent être extraites depuis les fichiers `.out`.

## Fichiers générés

Les résultats sont rangés par scénario, puis par temps de retour, puis par phase:

```powershell
MASS_COMPUTATION\runs\scenario1\T3
MASS_COMPUTATION\runs\scenario1\T10
MASS_COMPUTATION\runs\scenario1\T30
MASS_COMPUTATION\runs\scenario1\T50
```

Chaque simulation dispose d'un sous-dossier contenant les fichiers:

- `.inp`: modèle SWMM généré pour la combinaison;
- `.rpt`: rapport texte SWMM;
- `.out`: résultats binaires SWMM.

Un fichier CSV de synthèse est généré pour chaque temps de retour:

```powershell
MASS_COMPUTATION\runs\scenario1\T3\T3_mass_simulations_results.csv
MASS_COMPUTATION\runs\scenario1\T10\T10_mass_simulations_results.csv
MASS_COMPUTATION\runs\scenario1\T30\T30_mass_simulations_results.csv
MASS_COMPUTATION\runs\scenario1\T50\T50_mass_simulations_results.csv
```

Chaque ligne du CSV correspond à une simulation. Les colonnes principales sont:

- identifiant de simulation;
- dossier de calcul;
- scénario;
- phase;
- combinaison de variantes;
- probabilité de la combinaison;
- temps de retour;
- avertissement de flooding;
- avertissement d'instabilité SWMM;
- débits maximums stabilisés aux exutoires.

Les exutoires suivis sont:

- `Fensterstollen`;
- `Entw_Stollen`;
- `Brunnmuehle(Teich)`;
- `TWT_Portail_Est_61+665`.

## Flooding et instabilités

Le script distingue les floods hydrauliquement significatifs des instabilités ponctuelles. Les floods très courts peuvent être assimilés à des artefacts numériques et sont filtrés selon les seuils définis en tête du script, notamment:

```python
FLOODING_MIN_HOURS = 6.0
```

Le CSV contient également des colonnes liées à la convergence SWMM:

- `swmm_instability_warning`;
- `swmm_not_converging_percent`;
- `swmm_instability_elements`.

Ces champs permettent d'identifier les simulations dont les résultats doivent être interprétés avec prudence.

## Graphiques par phase

Le script de simulation génère des graphiques HTML par phase dans:

```powershell
MASS_COMPUTATION\runs\plots
```

Le nom des fichiers suit la logique:

```txt
1_T3_1a_debits_vs_probability.html
1_T10_4b_debits_vs_probability.html
```

Chaque page affiche les débits maximums stabilisés en fonction de la probabilité de la combinaison, avec un graphique par exutoire.

Les graphiques incluent:

- une échelle logarithmique en probabilité;
- une ligne verticale au seuil `MIN_COMBINATION_PROBABILITY`;
- une ligne horizontale correspondant au débit de la combinaison la plus probable;
- des lignes de référence issues des mesures disponibles pour Fensterstollen, Entw_Stollen et Brunnmuehle(Teich).

## Graphiques de synthèse

Les graphiques de synthèse sont générés par le script:

```powershell
D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\plot_all_phase_probability_envelopes.py
```

La commande de génération est:

```powershell
cd D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM
C:\Users\ISSKA\anaconda3\envs\spyder\python.exe plot_all_phase_probability_envelopes.py
```

Ce script lit les CSV T3, T10, T30 et T50, puis génère deux familles de pages HTML.

La première famille agrège toutes les phases et représente les débits en fonction de la probabilité:

```txt
1_T3_All_debits_vs_probability.html
1_T10_All_debits_vs_probability.html
1_T30_All_debits_vs_probability.html
1_T50_All_debits_vs_probability.html
```

Les valeurs sont regroupées par classes logarithmiques fines, par exemple `[1e-4, 2e-4)`, `[2e-4, 3e-4)`, etc. Chaque classe est représentée par un whisker plot:

- moustaches: minimum et maximum;
- boîte: Q1 à Q3;
- trait central: médiane.

La deuxième famille représente les débits par phase et par classe de probabilité:

```txt
1_T3_All_debits_by_phase_probability.html
1_T10_All_debits_by_phase_probability.html
1_T30_All_debits_by_phase_probability.html
1_T50_All_debits_by_phase_probability.html
```

Pour chaque phase ou sous-phase, quatre whisker plots sont affichés:

| Classe | Intervalle | Couleur |
| --- | --- | --- |
| P 1e-1 | `[1e-1, 1]` | rose |
| P 1e-2 | `[1e-2, 1e-1)` | violet |
| P 1e-3 | `[1e-3, 1e-2)` | jaune |
| P 1e-4 | `[1e-4, 1e-3)` | gris |

## Scénario Centrale Ventilation

Un second workflow permet d'évaluer le débit au droit de `CentraleVentilation_1C`. Il est piloté par le script:

```powershell
D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\MASS_COMPUTATION\run_swmm_centrale_ventilation_discharge.py
```

Ce workflow ne repart pas du modèle de base. Il reprend les fichiers `.inp` déjà générés pour la fin du percement du tunnel, c'est-à-dire les simulations de la phase `1_8a`:

```powershell
MASS_COMPUTATION\runs\scenario1\T3\1_8a
MASS_COMPUTATION\runs\scenario1\T10\1_8a
MASS_COMPUTATION\runs\scenario1\T30\1_8a
MASS_COMPUTATION\runs\scenario1\T50\1_8a
```

Pour chaque simulation source de `1_8a`, le script génère trois nouvelles simulations avec une variante de connexion nommée. Le nom de variante est conservé dans le CSV et dans le dossier de simulation afin de pouvoir retrouver facilement le cas calculé.

| Variante | Connexion SWMM | Junction cible | Probabilité |
| --- | --- | --- | ---: |
| `1_1C_0` | aucune connexion | - | 0.84 |
| `1_1C_1` | `CV_1C_to_52` | `52` | 0.10 |
| `1_1C_2` | `CV_1C_to_38` | `38` | 0.05 |
| `1_1C_3` | `CV_1C_to_54` | `54` | 0.01 |

La variante `1_1C_0` est le cas résiduel sans connexion. Sa probabilité est déduite automatiquement:

```txt
P(1_1C_0) = 1 - 0.10 - 0.05 - 0.01 = 0.84
```

Ces paramètres sont définis dans:

```powershell
D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\MASS_COMPUTATION\scenarios_CentraleVentilation.txt
```

Le fichier indique explicitement le scénario source et le dossier de sortie:

```txt
source_scenario scenario1
output_run_dir CV_scenario_1
```

Dans les fichiers `.inp` générés, `CentraleVentilation_1C` est converti en exutoire SWMM: la ligne est retirée de `[JUNCTIONS]` puis ajoutée à `[OUTFALLS]` avec une altitude de `454 m`. Les coordonnées de référence sont lues dans:

```powershell
D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM\260508_Coord_nodes_SWMM.xlsx
```

Les longueurs des conduits de connexion sont calculées à partir des coordonnées de ce fichier Excel. Les propriétés par défaut des connexions sont:

| Paramètre | Valeur |
| --- | ---: |
| Rugosité | 0.05 |
| Diamètre | 0.5 m |
| Géométrie | `CIRCULAR` |

Le débit maximum stabilisé est extrait sur cet exutoire comme:

```txt
Débit stabilisé = TOTAL_INFLOW stabilisé à CentraleVentilation_1C
```

Comme pour les débits aux autres exutoires, la valeur utilisée est extraite du fichier `.out` et stabilisée avec la même logique que le script principal. Elle ne correspond donc pas à un pic instantané du `.rpt`.

La commande de test, sans lancer SWMM, est:

```powershell
cd D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM
C:\Users\ISSKA\anaconda3\envs\spyder\python.exe MASS_COMPUTATION\run_swmm_centrale_ventilation_discharge.py --dry-run
```

La commande de lancement complète est:

```powershell
cd D:\Users\ISSKA\Documents\GitHub\Twanntunnel_Hydraulic_SWMM
C:\Users\ISSKA\anaconda3\envs\spyder\python.exe MASS_COMPUTATION\run_swmm_centrale_ventilation_discharge.py --workers 6
```

Les résultats sont enregistrés dans:

```powershell
MASS_COMPUTATION\runs\CV_scenario_1
```

Le fichier CSV de synthèse est:

```powershell
MASS_COMPUTATION\runs\CV_scenario_1\CV_scenario_1_discharge_results.csv
```

Chaque ligne du CSV correspond à une simulation `1_8a` source combinée avec une variante de connexion. Les colonnes principales sont:

- temps de retour;
- simulation source de la phase `1_8a`;
- combinaison de variantes du scénario 1;
- probabilité de la combinaison source;
- variante de connexion de `CentraleVentilation_1C`;
- nom du conduit de connexion SWMM;
- probabilité de la connexion;
- probabilité combinée;
- longueur, diamètre et rugosité du conduit de connexion;
- débit maximum stabilisé à l'exutoire.

## Précautions d'interprétation

Les comparaisons entre T3, T10, T30 et T50 ne sont valables que si les quatre volées de calcul ont été produites avec le même fichier `scenarios.txt`.

Si une variante est modifiée entre deux volées de calcul, par exemple un diamètre de conduit, les résultats ne sont plus directement comparables. Dans ce cas, il faut relancer les temps de retour déjà calculés avec la version actuelle du fichier de scénarios.

Il est également recommandé de vérifier les simulations présentant:

- un taux élevé de pas de temps non convergents;
- des instabilités reportées par SWMM;
- des débits ponctuellement supérieurs au débit total injecté;
- des différences de routage inattendues entre exutoires.

## Résultats publiés

Les fichiers HTML générés dans `MASS_COMPUTATION\runs\plots` peuvent être intégrés dans Docusaurus avec des `iframe`. Exemple:

```html
<iframe
  src="/Twanntunnel_Hydraulic_SWMM/1_T3_All_debits_by_phase_probability.html"
  width="100%"
  height="800px"
  frameBorder="0"
></iframe>
```

Les fichiers doivent être régénérés après chaque nouvelle volée de simulations pour que les graphiques restent synchronisés avec les CSV.
