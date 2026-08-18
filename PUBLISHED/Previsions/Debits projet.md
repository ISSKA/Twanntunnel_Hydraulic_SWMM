Les **débits projets** considérés pour les simulations sont les suivants:  T3, T10, T30 et T50. Les tableaux suivants donnent aussi les valeurs pour des temps plus longs: T100 et T300 ans.
- Les débits T0.5, T1, T2, T3, T5 et T10 sont évalués sur la base des mesures.
- Les débits T30, T50, T100 et T300 sont extrapolés selon trois variantes:

    - Une **loi de Gumbel** dont l'extrapolation est trés prudente. Il s'agit probablement du débit minimum attendu pour les temps de retour considérés.
    - Une variante "**prudente**", sur base logarithmique ("**log**"): 
        > Q = a + b ln(T).
    
        Elle représente plutôt une estimation prudente pour les grands temps de retour.

    - Une variante plus "**extrême**", sur base exponentielle ("**exp**") : 
        > Q = exp(a) * T^b. 

        Cette variante permet une croissance plus rapide des débits.

Le tableau ci-dessous présente les valeurs de débits considérés pour les temps de retour listés plus haut. Le graphique des valeurs est affiché plus bas. Les valeurs <mark>surlignées</mark> sont celles utilisées pour les simulations. Il s'agit de valeurs de débits approximées par la loi de Gumbel, qui propose une extrapolation trés prudente des débits en fonction des temps de retour. 

| T      | Statut          | Gumbel    | Log (prudente) | Exp (extrême) |
| ------ | --------------- | --------- | -------------- | ------------- |
| 0.5    | Approximé       | n/a       | 7.53           | 8.60          |
| 1      | limite / mesuré | n/a       | 10.21          | 10.41         |
| 2      | mesuré          | 13.25     | 12.59          | 12.89         |
| 3      | mesuré          | <mark>14.71</mark> | 14.07          | 14.47         |
| 5      | mesuré          | 16.34     | 16.18          | 16.43         |
| 10     | mesuré          | <mark>18.38</mark> | 19.11          | 19.57         |
| 30     | extrapolé       | <mark>21.46</mark> | 23.36          | 26.46         |
| 50     | extrapolé       | <mark>22.9</mark>  | 25.30      | 30.40     |
| 100    | extrapolé       | 24.78     | 28.02          | 36.83         |
| 300    | extrapolé       | 27.77     | 32.26          | 49.79         |

 
> [!IMPORTANT]
> Les valeurs **T30**, **T50**, **T100** et **T300** sont toutes les quatre extrapolées! **T300** est très fortement extrapolé car l’ajustement repose sur **7 maxima annuels**, avec un temps de retour empirique maximal d’environ 12.7 ans...
> 
> Il est important de noter que ces valeurs sont des **"débits hydrologiques"**, c.à.d. fonction de la recharge appliqué sur le bassin. Ils ne doivent pas être confondus avec les débits **instantanés  considérés** qui peuvent survenir lors du percement d'un volume noyée (une "**poche**"). Ces débits instantanés peuvent être beaucoup plus élevées, mais sur des temps plus courts - fonction du volume à vidanger. 
> 
> A noter que dans des conditions défavorables, les deux types de débit peuvent s'additionner...

<iframe src="/Twanntunnel_Hydraulic_SWMM/Discharge_Input_SWMM_Gumbel.html"
    width="100%"
    height="800px"
    frameBorder="0"
></iframe>