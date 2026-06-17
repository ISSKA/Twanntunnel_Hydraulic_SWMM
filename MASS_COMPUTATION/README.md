# Simulations SWMM par scenarios

Ce dossier contient une premiere base pour lancer des simulations SWMM en masse a partir de `SWMM_Twannbach.inp`.

## Fichiers

- `run_swmm_mass_computation.py`: genere les fichiers `.inp`, lance SWMM, lit les `.out` et extrait les debits maximums stables.
- `scenarios.txt`: exemple de definition des situations hydrologiques, phases et variantes.
- `runs/`: dossier cree automatiquement avec un sous-dossier par simulation.

## Lancement

Depuis la racine du depot:

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

Pour limiter l'extraction a quelques conduits:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --links 69 70 Amont_L
```

Par defaut, le script lance uniquement les combinaisons finales de la derniere phase. Avec 8 phases et 3 variantes par phase, cela donne `3^8 = 6561` combinaisons, avant multiplication par les 3 hydrologies.

Pour lancer aussi les combinaisons intermediaires de chaque phase:

```powershell
python MASS_COMPUTATION\run_swmm_mass_computation.py --all-phases
```

Dans ce mode, le nombre de combinaisons par phase est:

- phase 1 avec 3 variantes: `3` combinaisons;
- phase 2 avec 3 variantes: `3 x 3 = 9` combinaisons;
- phase 3 avec 3 variantes: `3 x 3 x 3 = 27` combinaisons.

Ces nombres sont ensuite multiplies par les situations hydrologiques declarees dans `scenarios.txt`.

## Principe de calcul du maximum stable

Le script evite les pics instantanes isoles en cherchant le maximum dans une fenetre de plusieurs pas de sortie. Par defaut:

- fenetre: `4` heures;
- au moins `3` points proches du pic;
- seuil proche du pic: `95 %` du maximum brut.

Ces constantes sont modifiables en haut de `run_swmm_mass_computation.py`.

## Format minimal de scenarios.txt

```text
timeseries seche timeseries/seche.dat
timeseries normale timeseries/normale.dat
timeseries hautes_eaux timeseries/hautes_eaux.dat

scenario scenario1

phase 1_1
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
