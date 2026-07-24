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
          type: 'category',
          label: 'Twanntunnel',
          items: [
            'Previsions/Twanntunnel/Generalites',
            'Previsions/Twanntunnel/Scenario_1',
            'Previsions/Twanntunnel/Scenario_2',
          ]
        },
        {
          type: 'category',
          label: 'Centrales Ventilation',
          items: [
            'Previsions/Centrales Ventilation/Generalites',
            'Previsions/Centrales Ventilation/Scenario_1',
          ]
        },
      ],
    },
  ],
};

export default sidebars;