---
slug: /
hide_table_of_contents: true
---

# Description du modèle hydraulique
Le modèle hydraulique "**Twannbach**" est construit à l'aide du logiciel **EPA Storm Water Management Model** ([SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm)). Il s'agit d'une mise à jour du premier modèle établi en 2016 pour l'évaluation des risques hydrogéologiques karstiques lors du percement de la galerie de sécurité du Tunnel de Ligerztunnel ("SiSto Ligerz").

L'objectif principal du modèle hydraulique "**Twannbach**" est d'évaluer les débits et charges hydrauliques associées en conditions de **hautes eaux**. 

Ce modèle est utilisé pour l'évaluation en phase "**travaux**" et en phase "**exploitation**", en fonction des **scénarios** envisagées pour le [percement du Twanntunnel](../Variantes_Constructives/Twanntunnel_Variantes.md) et pour [l'excavation des centrales de ventilation](../Variantes_Constructives/Twanntunnel_Centrales_Ventilation.md).   

## Architecture

Le modèle se compose d'un réseau de "conduits" et de "junctions". Les conduits sont soit des conduits karstiques, soit des galeries artificielles, les junctions réprésentent les noeuds d'écoulement entre chaque conduits. 

Les conduits affichent les propriétés suivantes:
- Géométrie (circulaire, rectangulaire, semi-circulaire, etc.)
- Longueur
- Diamètre
- Rugosité

Les junctions (ou noeuds) possèdent les propriétés suivantes:
- Coordonnées X, Y
- Altitude

En première instance, le modèle hydraulique intègre les objets et ouvrages existants suivants:
- Les cavités karstiques du Wasserhooliloch, Gischeren et Schüttstein (exutoires temporaires de crue)
- Le Sondierstollen (et les venues d'eau associées SS1, SS3, SS4, SS6, etc.), le Fensterstollen et l'Entwaesserungstollen
- Les sources de Brunnmühle, Sauser et autres sources sous-lacustres
- Le Brunnmühle Fassung

Comme le modèle est supposé évoluer en fonction du percement du Twanntunnel. Il est donc prévu d'ajouter des noeuds et des conduits et de modifier leur propriétés pour simuler des réponses hydrauliques en fonction de l'avancement, selon les variantes constructives retenues.

## Aperçu

<iframe 
    src="./SWMM_Twannbach_3d.html"
    width="100%"
    frameborder="0"
></iframe>

Le modèle affiche les junctions et les conduits:
- Les junctions de type **cube** représentent les junctions dont la position est certaine ("**Fixed**"). Les junctions de type **sphère** représentent les junctions dont la position peut être modifiée ("**NotFixed**")
- Les **junctions classiques** sont colorées en noir, les **outfalls** en rouge
- Les conduits sont colorés selon le ratio Longueur_Euclidienne / Longueur_SWWM
    - Si **Ratio < 0.6** (la longueur euclidienne est trés inférieure à la longueur de conduits saisie dans SWMM), le conduit apparait **rouge**
    - Si **0.6 < Ratio < 1.4** (la longueur euclidienne équivaut à la longueur saisie dans SWWM), le conduit apparait **gris**
    - Si **1.4 < Ratio** (longueur saisie dans SWMM trés inférieure à la longueur euclidienne), le conduit apparait en **bleu**

> [!WARNING] 
> Actuellement la représentation 3D est légèrement faussée car les conduits sont connectés aux junctions par leur axe central alors qu'ils devraient normalement être connectés aux junctions par le radier!