import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    {
      type: 'category',
      label: 'Modèle hydraulique',
      items: [
        'Modele_Hydraulique/Description',
        'Modele_Hydraulique/Calibration',
        'Modele_Hydraulique/Simulations',
      ],
    },
    {
      type: 'category',
      label: 'Prévisions',
      items: [
        'Prévisions/Débits projet',
        'Prévisions/Twanntunnel',
        'Prévisions/Centrales ventilation',
      ],
    },
    {
      type: 'category',
      label: 'Variantes constructives',
      items: [
        'Variantes_Constructives/Twanntunnel_Variantes',
        'Variantes_Constructives/Twanntunnel_Centrales_Ventilation',
      ],
    },
  ],
};

export default sidebars;