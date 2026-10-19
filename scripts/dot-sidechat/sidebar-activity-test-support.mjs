import { build } from 'esbuild';
export async function sidebarActivityBundle() {
  return await build({
    entryPoints: ['scripts/dot-sidechat/sidebar-activity-fixture.tsx'],
    bundle: true,
    write: false,
    jsx: 'automatic',
    alias: {
      '@vibe/ui': './packages/ui/src',
      react: './packages/ui/node_modules/react',
      'react-dom': './packages/ui/node_modules/react-dom',
    },
    plugins: [
      {
        name: 'fixture-translations',
        setup(b) {
          b.onResolve({ filter: /^react-i18next$/ }, () => ({
            path: 'i18n',
            namespace: 'fixture',
          }));
          b.onLoad({ filter: /.*/, namespace: 'fixture' }, () => ({
            contents: `export function useTranslation(){return {t:k=>({'common:workspaces.needsAttention':'Needs Attention','common:workspaces.running':'Running','common:workspaces.idle':'Idle'}[k]??k)}}`,
            loader: 'js',
          }));
        },
      },
    ],
  });
}
