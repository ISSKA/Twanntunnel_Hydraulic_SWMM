Les **débits projets** considérés pour les simulations sont les suivants: T0.5, T1, T2, T3, T5, T10, T30, T100 et T300 ans.
- Les débits T0.5, T1, T2, T3, T5 et T10 sont évalués sur la base des mesures.
- Les débits T30, T100 et T300 sont extrapolés selon deux variantes:
    - Une variante "**prudente**", sur base logarithmique ("**log**"): 
        > Q = a + b ln(T).
    
        Elle représente plutôt une estimation prudente pour les grands temps de retour.

    - Une variante plus "**extrême**", sur base exponentielle ("**exp**") : 
        > Q = exp(a) * T^b. 

        Cette variante permet une croissance plus rapide des débits.

Le tableau ci-dessous présente les valeurs de débits considérés pour les temps de retour listés plus haut. Le graphique des valeurs est affiché plus bas.

| T   | Statut          | Gumbel | Log (prudente) | Exp (extrême) |
| --- | --------------- | ------ | -------------- | ------------- |
| 0.5 | Approximé       | n/a    | 7.53           | 8.60          |
| 1   | limite / mesuré | n/a    | 10.21          | 10.41         |
| 2   | mesuré          | 13.25  | 12.89          | 12.59         |
| 3   | mesuré          | 14.71  | 14.46          | 14.07         |
| 5   | mesuré          | 16.34  | 16.43          | 16.18         |
| 10  | mesuré          | 18.38  | 19.11          | 19.57         |
| 30  | extrapolé       | 21.46  | 23.36          | 26.46         |
| 100 | extrapolé       | 24.78  | 28.02          | 36.83         |
| 300 | extrapolé       | 27.77  | 32.26          | 49.79         |

> [!NOTE]  
> La valeur **T0.5** est peu standard dans l'approche de type Gumbel, elle est donc approximée.
  
> [!IMPORTANT]
> Les valeurs **T30**, **T100** et **T300** sont toutes trois extrapolées! **T300** est très fortement extrapolé car l’ajustement repose sur **7 maxima annuels**, avec un temps de retour empirique maximal d’environ 12.7 ans.

<iframe src="/Twanntunnel_Hydraulic_SWMM/Discharge_Input_SWMM_Gumbel.html"
    width="100%"
    height="800px"
    frameborder="0"
></iframe>