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
        {
          type: 'doc',
          id: 'Previsions/Debits projet',
          label: 'Débits projet',
        },
        {
          type: 'doc',
          id: 'Previsions/Twanntunnel',
          label: 'Twanntunnel',
        },
        {
          type: 'doc',
          id: 'Previsions/Centrales ventilation',
          label: 'Centrales ventilation',
        },
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