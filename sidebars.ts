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
            {
              type: 'category',
              label: 'Scénario 1',
              items: [
                'Previsions/Twanntunnel/Scenario_1/Description',
                {
                  type: 'category',
                  label: 'Résultats',
                  items: [
                    'Previsions/Twanntunnel/Scenario_1/Resultats/T3',
                    'Previsions/Twanntunnel/Scenario_1/Resultats/T10',
                    'Previsions/Twanntunnel/Scenario_1/Resultats/T30',
                    'Previsions/Twanntunnel/Scenario_1/Resultats/T50',
                  ]
                },
              ]
            },
            {
              type: 'category',
              label: 'Scénario 2',
              items: [
                'Previsions/Twanntunnel/Scenario_2/Description',
              ]
            },
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