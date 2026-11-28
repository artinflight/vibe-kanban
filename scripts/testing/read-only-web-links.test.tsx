import assert from 'node:assert/strict';
import { test } from 'node:test';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { LexicalComposer } from '../../packages/ui/node_modules/@lexical/react/LexicalComposer.dev.mjs';
import { RichTextPlugin } from '../../packages/ui/node_modules/@lexical/react/LexicalRichTextPlugin.dev.mjs';
import { ContentEditable } from '../../packages/ui/node_modules/@lexical/react/LexicalContentEditable.dev.mjs';
import { LexicalErrorBoundary } from '../../packages/ui/node_modules/@lexical/react/LexicalErrorBoundary.dev.mjs';
import { TRANSFORMERS } from '../../packages/ui/node_modules/@lexical/markdown/LexicalMarkdown.dev.mjs';
import { CodeNode } from '../../packages/ui/node_modules/@lexical/code/LexicalCode.dev.mjs';
import { LinkNode } from '../../packages/ui/node_modules/@lexical/link/LexicalLink.dev.mjs';
import { MarkdownSyncPlugin } from '../../packages/ui/src/components/MarkdownSyncPlugin';
import { ReadOnlyWebLinkPlugin } from '../../packages/ui/src/components/ReadOnlyWebLinkPlugin';
import { ReadOnlyLinkPlugin } from '../../packages/ui/src/components/ReadOnlyLinkPlugin';

function Chat({
  value,
  editable = false,
}: {
  value: string;
  editable?: boolean;
}) {
  return (
    <LexicalComposer
      initialConfig={{
        namespace: 'links-test',
        nodes: [CodeNode, LinkNode],
        onError: (error) => {
          throw error;
        },
      }}
    >
      {!editable && <ReadOnlyWebLinkPlugin />}
      <MarkdownSyncPlugin
        value={value}
        editable={editable}
        transformers={TRANSFORMERS}
      />
      <RichTextPlugin
        contentEditable={<ContentEditable />}
        placeholder={null}
        ErrorBoundary={LexicalErrorBoundary}
      />
      {!editable && <ReadOnlyLinkPlugin />}
    </LexicalComposer>
  );
}

const fixtures: [string, string[]][] = [
  [
    'Preview URL:: Updated https://preview.example.invalid:8443/',
    ['https://preview.example.invalid:8443/'],
  ],
  [
    'PR:: https://github.com/example/repo/pull/42',
    ['https://github.com/example/repo/pull/42'],
  ],
  [
    'Preview URL:: `https://preview.example.invalid/`',
    ['https://preview.example.invalid/'],
  ],
  [
    'Preview <https://preview.example.invalid/>',
    ['https://preview.example.invalid/'],
  ],
  [
    'Preview [Open preview](https://preview.example.invalid/)',
    ['https://preview.example.invalid/'],
  ],
  ['[Local preview](http://localhost:3000/)', ['http://localhost:3000/']],
  [
    'http://127.0.0.1:3000/ and https://example.invalid/?a=1&b=2#section',
    ['http://127.0.0.1:3000/', 'https://example.invalid/?a=1&b=2#section'],
  ],
  [
    'See (https://example.invalid/preview). Also https://example.invalid/wiki/Topic_(detail).',
    [
      'https://example.invalid/preview',
      'https://example.invalid/wiki/Topic_(detail)',
    ],
  ],
  ['**https://example.invalid/**', ['https://example.invalid/']],
  ['`curl https://example.invalid/`', []],
  ['```sh\ncurl https://example.invalid/\n```', []],
  [
    '[command](javascript:alert) [data](data:text/html,hello) [file](file:///tmp/test) [relative](/tmp/test)',
    [],
  ],
  ['javascript:https://example.invalid/ https://', []],
  [
    '[https://label.invalid/](https://destination.invalid/)',
    ['https://destination.invalid/'],
  ],
];

for (const [value, urls] of fixtures) {
  test(`first render: ${value}`, async () => {
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    try {
      await act(async () => {
        root.render(<Chat value={value} />);
      });
      const links = Array.from(
        host.querySelectorAll<HTMLAnchorElement>('a[href]')
      );
      assert.deepEqual(
        links.map((link) => link.getAttribute('href')),
        urls
      );
      for (const link of links) {
        assert.equal(link.target, '_blank');
        assert.equal(link.rel, 'noopener noreferrer');
        assert.notEqual(link.style.pointerEvents, 'none');
        assert.equal(link.getAttribute('aria-disabled'), null);
      }
      if (value.includes('`https://')) assert.ok(host.querySelector('a code'));
    } finally {
      await act(async () => root.unmount());
      host.remove();
    }
  });
}

test('streamed replacement and later turns remain clickable without resending', async () => {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  try {
    for (const value of [
      'https://',
      'https://example.invalid/first',
      '[next](http://localhost:3000/)',
      'https://example.invalid/second',
      'No preview',
    ]) {
      await act(async () => {
        root.render(<Chat value={value} />);
      });
      const expected = value.includes('invalid/')
        ? value
        : value.startsWith('[next]')
          ? 'http://localhost:3000/'
          : null;
      assert.equal(
        host.querySelector('a[href]')?.getAttribute('href') ?? null,
        expected
      );
    }
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});

test('the editable composer preserves a plain URL as text', async () => {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => {
      root.render(<Chat value="https://example.invalid/" editable />);
    });
    assert.equal(host.querySelector('a'), null);
    assert.equal(host.textContent, 'https://example.invalid/');
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});
