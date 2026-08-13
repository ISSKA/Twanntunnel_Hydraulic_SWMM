## Tronçons

Le tracé du Twanntunnel a été découpé en **7 tronçons** depuis le portail Est. Les caractéristiques des tronçons sont présentées dans le tableau suivant. 

>Le **Z "chaussée"** est l'altitude du radier lors du percement de **la calotte**
>Le **Z "radier"** est l'altitude du radier  lors du percement du **Stross**

| Nr. | Tronçon                                                   | Longueur [m] | Atlitude                                                  | Sens percement          |
| --- | --------------------------------------------------------- | ------------ | --------------------------------------------------------- | ----------------------- |
| 1   | Portail Est (61+665) vers  Chrosweg (61+140)              | 515          | Z chaussée : 425.6-436 m, Z radier : 421.6-432 m       | Ascendant               |
| 2   | Chrosweg (61+140) vers PointHaut (60+650)                 | 490          | Z chaussée : 436-442.5 m, Z radier : 432-438.5 m        | Ascendant               |
| 3   | PointHaut (60+650) vers Branche Est SonSto (60+540 )      | 110          | Z chaussée : 442.5-442.4 m, Z radier : 438.5-438.4 m   | Descendant              |
| 4   | Branche Est SonSto (60+540) vers Fensterstollen (60+375)  | 165          | Z chaussée : 442.4-441.3 m, Z radier : 438.4-437.3 m   | Descendant              |
| 5   | Fensterstollen (60+375) vers intersection Sonsto (60+345) | 30           | Z chaussée : 441.3-441 m, Z radier : 437.3-437 m        | Descendant              |
| 6   | Intersection Sonsto (60+345) vers Accès LT (60+110)       | 245          | Z chaussée : 441-441.5 m, Z radier : 437-437.5 m        | Descendant et remontant |
| 7   | Accès LT (60+110) vers Liaison LT (59+738)                | 372          | Z chaussée : 441.5-450.6 m, Z radier : 437.5 – 446.5 m | Ascendant               |
## Scénarios
Les sections suivantes affichent **les prévisions de débit** intercepté par l'ouvrage en fonction:
- des **scénarios** d'excavation,
- des **conditions hydrologiques** (ou [débits projets](obsidian://open?vault=PUBLISHED&file=Pr%C3%A9visions%2FD%C3%A9bits%20projet)) définies,
- des **phases** d'avancement des travaux pour le **scénario** considéré (**percement de la calotte** et/ou **excavation du Stross**) et des éventuelles **sous-phases** identifiées.
- des **variantes de recoupement** possibles pour chacune des phases. Une **probabilité** est assignée à chacune des variantes. 

Les résultats sont donnés à chaque exutoire considéré pour le drainage, et pour les différentes conditions hydrologiques (surtout T10, T30, T100 et T300):
- **Entwaesserungstollen**, 
- **Fensterstollen**,
- **Portail Est**.

Les informations relatives au percement du tunnel et susceptibles d'avoir un impact sur **l'évaluation hydraulique** sont les suivantes:
- Percement depuis le **portail Est** en phase **montante**, **descendante** sous le Twannbach, puis **remontante** pour jonctionner avec le Ligerztunnel; 
- Percement de la **calotte** dans un premier temps et excavation du **Stross** dans un second temps; 
- Intersection du Twanntunnel avec le Sondierstollen; 
- Intersection du Twanntunnel avec le Fensterstollen (le radier du stross du Twanntunnel se trouvera plus bas que le radier de la galerie du Fensterstollen).

Les **contraintes hydrauliques** sont suivantes:
- Privilégier le drainage des eaux vers les portails Est et Entwaesserungstollen (pour traitement). 
- Pas de traitement des eaux possible au niveau du Fensterstollen.
- Percement en descente sous la zone du Twannbach, donc potentiel risque d'ennoiement.
## Principes de calcul des prévisions
### Combinaisons
Les prévisions sont basées sur de multiples simulations du modèle hydraulique SWMM en intégrant les différentes combinaisons possibles des variantes, phase après phase. 
Par exemple: 
- Scénario 1:
	- Combinaison 1_1_a_1 : 
		- Phase 1a:
			- Variante 1a_1: 
				- Recoupement d'un conduit connecté aux branches amont du système Est, de diamètre 1 m et de longueur 10 m. La probabilité de ce recoupement est de 0.15
	- Combinaison 1_1a_3 :
		- Phase 1a:
			- Variante 1a_3:
				- Recoupement d'un conduit connecté au Wasserhooliloch, de diamètre 1 m et de longueur 750 m. La probabilité de ce recoupement est de 0.01.
	- Combinaison 1_1a-1_1a_1+1_1a_3:
		- Phase 1a:
			- Variante 1a_1 + Variante 1a_3:
				- Recoupement d'un conduit connecté  aux branches amont du système Est, (diamètre 1 m et longueur 10 m) **et** recoupement d'un conduit connecté au Wasserhooliloch (diamètre 1 m et longueur 750 m). La probabilité de ce recoupement est de 0.0013.
	- Combinaison 1_1a-1_1a_2__1_1b-1_1b_1+1_1b_2+1_1b_3:
		- Phase 1b:
			- Variante 1a_2 (phase 1a) + Variante 1b_1 (phase 1b) + Variante 1b_2 (phase 1b) + Variante 1b_3 (phase 1b). La probabilité de cette variante est de 0.00011.
	- etc.

## Probabilité
Les probabilités de recoupement sont définies par tronçon en fonction de la longueur respective du tronçon. Elles sont ensuite combinées en supposant que les variantes actives d’une même phase sont indépendantes.

Ainsi, pour une phase donnée: 
```
P(V1 + V2) = P(V1) x P(V2) x (1 - P(V3)) x ...
```

Entre les phases successives, les probabilités sont multipliées:
```
P(combinaison totale) =
P(combinaison phase 1)
x P(combinaison phase 2)
x P(combinaison phase 3)
...
```

Les variantes "sans recoupement", typiquement les variantes **1_1a_0**, **1_1b_0**, etc. ne se voient pas assigner de probabilité propre. Leur probabilité est déduite automatiquement à partir des variantes actives de la phase (produit des **(1 - prob)**).

Ainsi, si: 
```
V1 prob=0.10
V2 prob=0.20
V3 prob=0.05
```

Alors:
```
P(V0) = (1 - 0.10) x (1 - 0.20) x (1 - 0.05)
      = 0.684
```
### Seuil de probabilité
Etant donné le nombre relativement important de phases et de variantes, les combinaisons possibles se chiffrent à environ $6.10^{12}$ simulations pour le **scénario 1**, et pour une **unique condition hydrologique** donnée, ce qui représente des temps de calculs considérables - surtout au regard d'un grand nombre de combinaisons de variantes de très faible probabilité. 
Ainsi, un seuil de probabilité admissible a été défini à ==$1.10^{-4}$,== ce qui signifie que les combinaisons dont la probabilité de se produire est inférieure à cette valeur ne sont pas reprises dans les combinaisons suivantes. 
En appliquant ce filtre, les combinaisons dont la probabilité de se produire dépasse le seuil de $1.10^{-4}$ sont estimées à environ 9'000.



