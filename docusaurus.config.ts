import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import { themes } from 'prism-react-renderer';
import remarkDirective from 'remark-directive';
import remarkGithubAdmonitions from './remark-github-admonitions';


const config: Config = {
  title: 'Twanntunnel Hydraulic SWMM',
  url: 'https://isska.github.io',
  baseUrl: '/Twanntunnel_Hydraulic_SWMM/',
  onBrokenLinks: 'throw',

  staticDirectories: ['static', 'PLOTS'],
  
  future: {
    v4: true,
  },

  organizationName: 'ISSKA',
  projectName: 'Twanntunnel_Hydraulic_SWMM',
  presets: [
    [
      'classic',
      {
        docs: {
          remarkPlugins: [remarkDirective, remarkGithubAdmonitions],
          routeBasePath: '/',
          path: 'PUBLISHED',
          sidebarPath: './sidebars.ts',
          showLastUpdateTime: true,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    navbar: {
      title: 'Twanntunnel Hydraulic SWMM',
    },
  } satisfies Preset.ThemeConfig,
};

export default config;