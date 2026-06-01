# Description des fichiers

## 260508_Coord_nodes_SWMM.xlsx

- Le fichier contient le nom des junctions et leurs coordonnées X et Y 
- Chaque junction est assignée avec une valeur "**Fixed**" si la position de la junction est certaine ou "**NotFixed**" si la position de la junction peut être déplacée
- Le nom de la junction est repris depuis le fichier **SWMM_Twannbach.inp**. Si le nom de la junction est modifiée ou si une nouvelle junction est ajoutée dans le fichier .inp, la modification doit être reportée dans le tableur.

## SWMM_Twannbach.inp

- Fichier d'input SWMM. 
- Les coordonnées X et Y des junctions sont indicatives, elles n'ont aucun sens en 3D ( ce sont les X et Y du fichier **260508_Coord_nodes_SWMM.xlsx** qui font foi)
- Attention en cas d'ajout de junction ou de modification de nom de junction

## Scripts

### visualize_swmm_3d.py

- le script utilise en entrée les fichiers **SWMM_Twannbach.inp** et **260508_Coord_nodes_SWMM.xlsx** pour générer: 
    - Un fichier de visualisation 3D .html **SWMM_Twannbach_3d.html**,
    - Un fichier 3D **SWMM_Twannbach_network.obj** pour intégration dans le projet **Cinema 4D**

### generate_tw_calibration.py

- Le script génère un fichier de calibration SWMM pour les junctions 
    - Wasserhooliloch, Gischeren, Schuetstein, SS1, SS3, SS4 et SS6 (hauteurs d'eau en m.a.s.l)
    - Source de Brunnmühle, Entwaesserungstollen et Fensterstollen (Débits en m3/s)
- Le fichier généré est de la forme **TW_Calibration.txt** (format ANSI). Il est enregistré dans le dossier > O:\Projets en cours\SCIENCE\Sci.387_N05TWT_Appui_ISSKA_GG\1_PRODUCTION\SWMM\CALIBRATION

### generate_swmm_timeseries.py

- Le script génère les débits d'input du modèle SWMM au pas de temps horaire sous la forme d'un fichier texte **Discharge_Input_SWMM.txt** (format ANSI)
- Le fichier **Discharge_Input_SWMM.txt** est enregistré dans le dossier  > O:\Projets en cours\SCIENCE\Sci.387_N05TWT_Appui_ISSKA_GG\1_PRODUCTION\SWMM
- Les régles de calcul des débits d'input sont les suivants: Débit_Brunnmuelhe + Débit_Entwaesserungstollen + Débit_Twannbach_Unten - Débit_Twannbach_Oben
- Le Débit_Twannbach_Oben est obtenu sur la base de l'équation y = 113759x5 - 182008x4 + 104604x3 - 20741x2 + 1430.1x (y étant des débits en l/s, x étant les niveaux en m) issue de la courbe de tarage du fichier > O:\Projets en cours\SCIENCE\SP_Twann_tunnel\2_Stations_mesure\Station_mesure_Twannbach Amont\Analyse_debit\Courbe de tarage_TbAM.xlsx
- La combinaison des mesures n'est effective que sur les plages de mesures sans lacunes de mesures > 48 h
- Idem, si le débit reconstitué du Twannbach_Oben est supérieur à celui du Twannbach_Unten, il n'est pas soustrait (sinon risque de débit négatif)
- Le script liste les plages de lacunes pour chacune des stations. 
- Le script génère un plot **Discharge_Input_SWMM_plot.html** dans le dossier > O:\Projets en cours\SCIENCE\Sci.387_N05TWT_Appui_ISSKA_GG\1_PRODUCTION\SWMM\INPUT

### generate_gumbel_return_period.py

Le script analyse la série horaire **Discharge_Input_SWMM.txt** et les débits maximums annuels disponibles. Ces maxima sont classés par ordre décroissant.
Un temps de retour empirique est attribué avec la formule de Gringorten et le script ajuste ensuite une loi de Gumbel aux maxima annuels. 

- Le script calcule les débits pour T0.5, T1, T2, T3, T5, T10, T30 et T100 ans et génère:
    - un tableau CSV **Discharge_Input_SWMM_Gumbel_values.csv** 
    - un graphique HTML **Discharge_Input_SWMM_Gumbel.html**.
- La courbe principale correspond à l’ajustement Gumbel. T30 et T100 sont extrapolés selon deux variantes :
    - Une variante "**prudente**", sur base **logarithmique** : Q = a + b ln(T). Elle représente plutôt une estimation prudente pour les grands temps de retour.
    - Une variante plus "**extrême**", sur base **exponentielle** : Q = exp(a) * T^b. Cette variante permet une croissance plus rapide des débits.
- T0.5 est indiqué comme non standard avec une approche par maxima annuels.
- Les plages de dates sont listées lorsque le seuil de débit est atteint dans la série.
 
## Fichiers 3D

### SWMM_Twannbach_3d.html

- Modèle 3D du réseau de conduits et de junctions SWMM généré par le script **visualize_swmm_3d.py** 
- Le fichier peut être ouvert directement sur le navigateur web
- Le modèle affiche les junctions et les conduits:
    - Les junctions de type **cube** représentent les junctions dont la position est certaine ("**Fixed**"). Les junctions de type **sphère** représentent les junctions dont la position peut être modifiée ("**NotFixed**")
    - Les **junctions classiques** sont colorées en noir, les **outfalls** en rouge
    - Les conduits sont colorés selon le ratio Longueur_Euclidienne / Longueur_SWWM
        - Si **Ratio < 0.6** (la longueur euclidienne est trés inférieure à la longueur de conduits saisie dans SWMM), le conduit apparait **rouge**
        - Si **0.6 < Ratio < 1.4** (la longueur euclidienne équivaut à la longueur saisie dans SWWM), le conduit apparait **gris**
        - Si **1.4 < Ratio** (longueur saisie dans SWMM trés inférieure à la longueur euclidienne), le conduit apparait en **bleu**
- Les géométries et diamètres des conduits sont reproduits.

> [!WARNING] 
> Actuellement la représentation 3D est légèrement faussée car les conduits sont connectés aux junctions par leur axe central alors qu'ils devraient normalement être connectés aux junctions par le radier!

### SWMM_Twannbach_network.obj
- Modèle 3D du réseau de conduits SWMM au format .obj pour intégration dans Cinema4D

> [!WARNING] 
> A l'import il est nécessaire de fixer le facteur de conversion à 0.1 mm


