import { useEffect } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { registerReadOnlyWebLinks } from '../lib/read-only-web-links';

/** Link agent URLs on the first render and as streamed Markdown is reparsed. */
export function ReadOnlyWebLinkPlugin() {
  const [editor] = useLexicalComposerContext();
  useEffect(() => registerReadOnlyWebLinks(editor), [editor]);
  return null;
}
