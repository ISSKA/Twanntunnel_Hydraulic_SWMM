# Simulations SWMM par scenarios

Ce dossier contient une premiere base pour lancer des simulations SWMM en masse a partir de `SWMM_Twannbach.inp`.

## Fichiers

- `run_swmm_mass_computation.py`: genere les fichiers `.inp`, lance SWMM, lit les `.out` et extrait les debits maximums stables.
- `scenarios.txt`: exemple de definition des situations hydrologiques, phases et variantes.
- `run_swmm_centrale_ventilation_discharge.py`: relance les modeles de fin de phase `1_8a` pour tester les connexions de la centrale de ventilation et extraire les debits stabilises.
- `scenarios_CentraleVentilation.txt`: definition des temps de retour, du noeud de controle et des variantes de connexion de la centrale de ventilation.
- `runs/`: dossier cree automatiquement avec un sous-dossier par scenario, puis par phase, puis par simulation.

## Lancement

Depuis la racine du depot, avec le Python QGIS disponible sur cette machine:

```powershell
& "C:\Program Files\QGIS 3.28.0\bin\python-qgis.bat" MASS_COMPUTATION\run_swmm_mass_computation.py --dry-run
```

Ou avec un Python classique:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --dry-run
```

Le `--dry-run` genere les `.inp` sans lancer SWMM. Pour lancer les simulations:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py
```

Si `epaswmm` ou `swmm-toolkit` n'est pas disponible dans l'environnement Python, passer un executable SWMM:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --engine "C:\chemin\vers\swmm5.exe"
```

Le script lit les resultats via `swmm-toolkit` si disponible. Sinon, il utilise le rapport `.rpt` de SWMM comme fallback pour les maxima aux exutoires et le flooding.

Par defaut, le script lance les combinaisons intermediaires de chaque phase:

```text
phase 1_1a: variantes 1_1a seulement
phase 1_1b: variantes 1_1a + variantes 1_1b
phase 1_2a: variantes 1_1a + variantes 1_1b + variantes 1_2a
```

Pour ne lancer que la derniere phase cumulee:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --final-phase-only
```

## Configuration actuelle

Le fichier `scenarios.txt` est configure pour:

- scenario `scenario1`;
- phases cumulees jusqu'a la phase indiquee par `stop_after_phase`;
- variantes combinees aussi a l'interieur de chaque phase via `combine_variants_within_phase yes`;
- hydrologie `T3`, soit un debit constant de `14.7 m3/s` injecte sur `Amont_C` / `Amont_L`;
- injection secondaire automatique de `Q/10` sur le noeud amont du conduit `48`;
- simulation horaire du `01/01/2000 00:00` au `02/01/2000 00:00`;
- extraction des debits maximums aux exutoires `Fensterstollen`, `Entw_Stollen`, `Brunnmuehle(Teich)` et `TWT_Portail_Est_61+665`.

Avec `combine_variants_within_phase yes`, les variantes peuvent aussi etre additionnees entre elles dans la meme phase. Les variantes sans action, typiquement `V0`, sont traitees comme des cas "sans modification": elles sont lancees seules mais ne sont pas combinees avec les variantes actives, car `V0+V1` est equivalent a `V1`.

Exemple avec 4 variantes dont une `V0` sans action: `1 + (2^3 - 1) = 8` branches.

Exemple avec 4, 4, 5 et 8 variantes par phase, chacune ayant une `V0` sans action:

- ancienne logique: `4 x 4 x 5 x 8 = 640`;
- nouvelle logique sans multiplier les doublons `V0`: `8 x 8 x 16 x 128 = 1'048'576`.

Le script bloque par defaut au-dessus de `100000` simulations pour eviter un lancement accidentel massif. Pour lancer quand meme:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --allow-large-run
```

Ou pour ajuster le seuil:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --max-cases 200000 --allow-large-run
```

Les combinaisons tres improbables sont filtrees par defaut:

```python
MIN_COMBINATION_PROBABILITY = 1e-4
```

Une combinaison cumulee est simulee et transmise a la phase suivante seulement si:

```text
combination_probability > 1e-4
```

Le seuil peut etre ajuste au lancement:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --min-combination-probability 5e-4
```

Pour desactiver le filtrage:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --min-combination-probability 0
```

Les temps de retour peuvent etre declares comme hydrologies constantes:

```text
constant_flow T3 14.7
constant_flow T10 18.4
constant_flow T30 21.5
constant_flow T50 22.9
```

Les valeurs T3, T10 et T30 proviennent du tableau Gumbel, avec arrondi au dixieme. T50 n'est pas liste explicitement dans le HTML Gumbel actuel; `22.9 m3/s` est interpole sur la courbe Gumbel.

Le CSV final `MASS_COMPUTATION\runs\scenario1\T3\T3_mass_simulations_results.csv` contient une ligne par simulation avec:

- `simulation_id`;
- `case_directory`;
- `phase`;
- `variant_combination`;
- `combination_probability`;
- les colonnes `qmax_*_m3s` pour les exutoires;
- `flooding_warning` et `flooding_nodes`.

Les resultats sont ranges par scenario, hydrologie/temps de retour, puis phase:

```text
MASS_COMPUTATION\runs\scenario1\T3\1_1a\sim_0001\
MASS_COMPUTATION\runs\scenario1\T3\1_1b\sim_0009\
MASS_COMPUTATION\runs\scenario1\T3\1_2a\sim_0073\
```

Le CSV de synthese est ecrit dans le dossier de l'hydrologie:

```text
MASS_COMPUTATION\runs\scenario1\T3\T3_mass_simulations_results.csv
```

Le script genere aussi un fichier HTML par phase dans le dossier central `MASS_COMPUTATION\runs\plots`. Le nom contient le scenario, le temps de retour et la phase:

```text
MASS_COMPUTATION\runs\plots\1_T3_1a_debits_vs_probability.html
MASS_COMPUTATION\runs\plots\1_T10_4b_debits_vs_probability.html
```

Chaque fichier trace les debits maximums aux exutoires en fonction de `combination_probability`, pour les combinaisons disponibles a cette phase uniquement.

## Scenario Centrale Ventilation

Le script `run_swmm_centrale_ventilation_discharge.py` sert a evaluer le debit a l'exutoire `CentraleVentilation_1C`, en repartant des simulations deja produites pour le scenario 1 en fin de percement du tunnel:

```text
MASS_COMPUTATION\runs\scenario1\T3\1_8a\
MASS_COMPUTATION\runs\scenario1\T10\1_8a\
MASS_COMPUTATION\runs\scenario1\T30\1_8a\
MASS_COMPUTATION\runs\scenario1\T50\1_8a\
```

Le fichier `scenarios_CentraleVentilation.txt` definit:

- le scenario source a reprendre: `source_scenario scenario1`;
- le dossier de sortie: `output_run_dir CV_scenario_1`;
- les temps de retour a reprendre: `T3`, `T10`, `T30` et `T50`;
- le noeud de controle `CentraleVentilation_1C`, avec une elevation imposee de `454 m`;
- les proprietes par defaut des conduits de connexion;
- les variantes de connexion vers les noeuds `52`, `38` et `54`.

Les probabilites actuellement retenues pour ces variantes de connexion sont:

```text
1_1C_0: no_connection prob=residual
1_1C_1: connection CV_1C_to_52 target=52 prob=0.1
1_1C_2: connection CV_1C_to_38 target=38 prob=0.05
1_1C_3: connection CV_1C_to_54 target=54 prob=0.01
```

La variante `1_1C_0` represente le cas sans connexion de la centrale de ventilation. Sa probabilite est deduite automatiquement:

```text
P(1_1C_0) = 1 - 0.1 - 0.05 - 0.01 = 0.84
```

Les coordonnees de `CentraleVentilation_1C` et des noeuds cibles sont lues dans:

```text
260508_Coord_nodes_SWMM.xlsx
```

Elles servent notamment a calculer automatiquement la longueur des nouveaux conduits. Pour chaque simulation source de `1_8a`, le script cree trois nouvelles simulations, une par connexion testee.

Dans les `.inp` generes, `CentraleVentilation_1C` est retire de `[JUNCTIONS]` et ajoute dans `[OUTFALLS]` avec une elevation de `454 m`. Le debit maximum stabilise est extrait sur cet exutoire via le `TOTAL_INFLOW` SWMM:

```text
debit stabilise = TOTAL_INFLOW stabilise a CentraleVentilation_1C
```

Pour controler le nombre de simulations sans lancer SWMM:

```powershell
C:\Users\ISSKA\anaconda3\envs\spyder\python.exe MASS_COMPUTATION\run_swmm_centrale_ventilation_discharge.py --dry-run
```

Pour lancer les calculs:

```powershell
C:\Users\ISSKA\anaconda3\envs\spyder\python.exe MASS_COMPUTATION\run_swmm_centrale_ventilation_discharge.py --workers 6
```

Les fichiers sont ecrits dans:

```text
MASS_COMPUTATION\runs\CV_scenario_1\
```

Ce dossier est defini dans `scenarios_CentraleVentilation.txt` par:

```text
output_run_dir CV_scenario_1
```

avec une arborescence par temps de retour, simulation source et variante de connexion:

```text
MASS_COMPUTATION\runs\CV_scenario_1\T10\1_8a\sim_1234\1_1C_1_CV_1C_to_52\
```

Le CSV de synthese est:

```text
MASS_COMPUTATION\runs\CV_scenario_1\CV_scenario_1_discharge_results.csv
```

Il contient notamment le temps de retour, la simulation source, la variante de connexion (`1_1C_0`, `1_1C_1`, `1_1C_2` ou `1_1C_3`), le nom du conduit SWMM, la probabilite de connexion et le debit maximum stabilise a l'exutoire.

## Performance

Les simulations sont independantes et peuvent etre lancees en parallele. Exemple prudent:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --workers 4 --use-rpt-only
```

- `--workers 4` lance 4 simulations SWMM en parallele.
- `--use-rpt-only` extrait les maxima et le flooding depuis les rapports `.rpt`, sans ouvrir les fichiers `.out`.

Si la machine reste reactive, augmenter progressivement a `--workers 6` ou `--workers 8`. Si elle devient lente ou si le disque sature, redescendre a `--workers 2` ou `--workers 4`.

## Principe d'extraction

Pour le cas actuel, le script extrait le debit maximum horaire aux quatre exutoires listes plus haut.

Le flooding est filtre pour eviter de signaler les instabilites numeriques tres courtes. Les seuils sont definis en haut du script:

```python
FLOODING_MIN_RATE_M3S = 0.01
FLOODING_MIN_CONSECUTIVE_STEPS = 2
FLOODING_MIN_HOURS = 6.0
```

Avec les fichiers `.out`, `flooding_warning=YES` demande au moins 2 pas de sortie consecutifs au-dessus de `0.01 m3/s`. Avec `--use-rpt-only`, le filtre utilise le resume SWMM: au moins 6 heures de flooding et un debit maximum au-dessus de `0.01 m3/s`.

## Format minimal de scenarios.txt

```text
constant_flow T3 14.7
# constant_flow T10 18.4
# constant_flow T30 21.465
# constant_flow T50 22.873

scenario scenario1
stop_after_phase 1_2_b
combine_variants_within_phase yes

phase 1_1_a
  variant V1
    set_diameter link=69 diameter=1.0

  variant V2
    add_conduit name=P1_1_A_51_52 from=51 to=52 length=120 roughness=0.01 diameter=1.2

  variant V3
    set_diameter link=70 diameter=1.2

phase 1_2
  variant V1
    set_diameter link=71 diameter=1.0

  variant V2
    set_diameter link=72 diameter=1.0

  variant V3
    set_diameter link=75 diameter=1.0
```

Les actions directement sous une phase sont communes a toutes les variantes de cette phase. Les actions sous une variante ne s'appliquent qu'a cette branche, mais elles sont reprises par toutes les phases suivantes de la meme combinaison.

Pour modifier une altitude de noeud:

```text
set_junction_elevation node=<junction_ou_outfall> elevation=<radier_m>
```

La commande cherche d'abord dans `[JUNCTIONS]`, puis dans `[OUTFALLS]`. Pour cibler explicitement un exutoire:

```text
set_outfall_elevation outfall=<outfall> elevation=<radier_m>
```

## Probabilites

Le champ optionnel `prob` peut etre place sur une ligne seule dans une variante sans action:

```text
variant 1_1a_0
  prob=0.71
```

ou sur une action de variante:

```text
variant 1_1a_1
  add_conduit name=... from=... to=... length=10 roughness=0.05 diameter=1 prob=0.15
```

Pour les variantes actives d'une meme phase, le script suppose des evenements independants:

```text
P(V1+V2) = P(V1) x P(V2) x (1 - P(V3)) x ...
```

La variante sans action, typiquement `V0`, utilise sa probabilite explicite si elle est renseignee. Sinon, elle est deduite avec le produit des `(1 - prob)` des variantes actives de la phase.

La colonne `combination_probability` du CSV multiplie ensuite les probabilites des phases cumulees.
