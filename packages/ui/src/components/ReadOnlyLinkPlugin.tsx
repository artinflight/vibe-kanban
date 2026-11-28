import { useEffect } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { LinkNode } from '@lexical/link';

/** Only web URLs are navigable; file paths and custom schemes stay disabled. */
function sanitizeHref(href?: string): string | undefined {
  if (!href || !/^https?:\/\//i.test(href.trim())) return undefined;
  try {
    const url = new URL(href.trim());
    if (url.protocol === 'https:' || url.protocol === 'http:')
      return href.trim();
  } catch {
    // Incomplete streaming URLs are not navigable yet.
  }
  return undefined;
}

function configureLink(link: HTMLAnchorElement) {
  const href = link.getAttribute('href');
  const safeHref = sanitizeHref(href ?? undefined);
  if (!safeHref) {
    link.removeAttribute('href');
    link.style.cursor = 'not-allowed';
    link.style.pointerEvents = 'none';
    link.setAttribute('role', 'link');
    link.setAttribute('aria-disabled', 'true');
    link.title = href ?? '';
    return;
  }

  // Clear disabled state if a streaming/reused node becomes a valid web link.
  link.setAttribute('href', safeHref);
  link.style.cursor = '';
  link.style.pointerEvents = '';
  link.removeAttribute('aria-disabled');
  link.removeAttribute('role');
  link.removeAttribute('title');
  link.setAttribute('target', '_blank');
  link.setAttribute('rel', 'noopener noreferrer');
  link.onclick = (event) => event.stopPropagation();
}

/**
 * Plugin that handles link sanitization and security attributes in read-only mode.
 * - Blocks dangerous protocols (javascript:, vbscript:, data:)
 * - External HTTP(S) links: clickable with target="_blank" and rel="noopener noreferrer"
 * - Internal/relative links: rendered but not clickable
 */
export function ReadOnlyLinkPlugin() {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    // Register a mutation listener to modify link DOM elements
    const unregister = editor.registerMutationListener(
      LinkNode,
      (mutations) => {
        for (const [nodeKey, mutation] of mutations) {
          if (mutation === 'destroyed') continue;

          const dom = editor.getElementByKey(nodeKey);
          if (!dom || !(dom instanceof HTMLAnchorElement)) continue;

          configureLink(dom);
        }
      }
    );

    // Also handle existing links on mount by triggering a read
    editor.getEditorState().read(() => {
      const root = editor.getRootElement();
      if (!root) return;

      const links = root.querySelectorAll('a');
      links.forEach(configureLink);
    });

    return unregister;
  }, [editor]);

  return null;
}
