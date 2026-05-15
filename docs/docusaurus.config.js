import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'JAM DSL',
  tagline: 'A music notation language that compiles to hardware',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://zer0hiro.github.io',
  baseUrl: '/JAM-DSL-Compiler/',

  organizationName: 'zer0hiro',
  projectName: 'JAM-DSL-Compiler',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/zer0hiro/JAM-DSL-Compiler/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themes: [
    [
      '@easyops-cn/docusaurus-search-local',
      /** @type {import("@easyops-cn/docusaurus-search-local").PluginOptions} */
      ({
        hashed: true,
        language: ['en'],
        indexBlog: false,
        docsRouteBasePath: '/docs',
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/docusaurus-social-card.jpg',
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'JAM DSL',
        logo: {
          alt: 'JAM DSL Logo',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            to: '/docs/guides/getting-started',
            label: 'Guides',
            position: 'left',
          },
          {
            href: 'https://github.com/zer0hiro/JAM-DSL-Compiler',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Documentation',
            items: [
              {
                label: 'Introduction',
                to: '/docs/intro',
              },
              {
                label: 'Language Reference',
                to: '/docs/language/global-config',
              },
              {
                label: 'Examples',
                to: '/docs/examples',
              },
            ],
          },
          {
            title: 'Guides',
            items: [
              {
                label: 'Getting Started',
                to: '/docs/guides/getting-started',
              },
              {
                label: 'Your First Song',
                to: '/docs/guides/first-song',
              },
              {
                label: 'Upload to Hardware',
                to: '/docs/guides/upload-to-hardware',
              },
            ],
          },
          {
            title: 'More',
            items: [
              {
                label: 'GitHub',
                href: 'https://github.com/zer0hiro/JAM-DSL-Compiler',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} JAM DSL. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
