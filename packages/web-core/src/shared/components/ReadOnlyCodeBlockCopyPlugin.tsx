import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { $isCodeNode, CodeNode } from '@lexical/code';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import {
  $getRoot,
  $isElementNode,
  type ElementNode,
  type RootNode,
} from 'lexical';
import { CodeBlockCopyButton } from '@/shared/components/CodeBlockCopyButton';

interface CodeBlockOverlay {
  key: string;
  text: string;
  top: number;
  left: number;
}

interface ReadOnlyCodeBlockCopyPluginProps {
  enabled?: boolean;
}

const BUTTON_SIZE = 32;
const BUTTON_INSET = 8;
const RESERVED_TOP_PADDING = '2.25rem';
const RESERVED_RIGHT_PADDING = '3rem';

export function ReadOnlyCodeBlockCopyPlugin({
  enabled = true,
}: ReadOnlyCodeBlockCopyPluginProps) {
  const [editor] = useLexicalComposerContext();
  const overlayRootRef = useRef<HTMLDivElement | null>(null);
  const styledBlocksRef = useRef<
    Map<
      HTMLElement,
      {
        paddingTop: string;
        paddingRight: string;
      }
    >
  >(new Map());
  const frameRef = useRef<number | null>(null);
  const [overlays, setOverlays] = useState<CodeBlockOverlay[]>([]);

  const restoreCodeBlock = useCallback((element: HTMLElement) => {
    const previous = styledBlocksRef.current.get(element);
    if (!previous) return;

    element.style.paddingTop = previous.paddingTop;
    element.style.paddingRight = previous.paddingRight;
    styledBlocksRef.current.delete(element);
  }, []);

  const styleCodeBlock = useCallback((element: HTMLElement) => {
    if (!styledBlocksRef.current.has(element)) {
      styledBlocksRef.current.set(element, {
        paddingTop: element.style.paddingTop,
        paddingRight: element.style.paddingRight,
      });
    }

    element.style.paddingTop = RESERVED_TOP_PADDING;
    element.style.paddingRight = RESERVED_RIGHT_PADDING;
  }, []);

  const syncCodeBlocks = useCallback(() => {
    if (!enabled) {
      setOverlays([]);
      return;
    }

    const editorRoot = editor.getRootElement();
    const overlayRoot = overlayRootRef.current;
    const positioningRoot = overlayRoot?.parentElement;
    if (!editorRoot || !overlayRoot || !positioningRoot) return;

    const positioningRect = positioningRoot.getBoundingClientRect();
    const currentElements = new Set<HTMLElement>();
    const nextOverlays: CodeBlockOverlay[] = [];

    editor.getEditorState().read(() => {
      const visitNode = (node: ElementNode | RootNode = $getRoot()) => {
        for (const child of node.getChildren()) {
          if ($isCodeNode(child)) {
            const element = editor.getElementByKey(child.getKey());
            const text = child.getTextContent().replace(/\n$/, '');

            if (element instanceof HTMLElement && text.trim()) {
              const rect = element.getBoundingClientRect();
              currentElements.add(element);
              styleCodeBlock(element);

              nextOverlays.push({
                key: child.getKey(),
                text,
                top: Math.max(0, rect.top - positioningRect.top + BUTTON_INSET),
                left: Math.max(
                  0,
                  rect.right - positioningRect.left - BUTTON_SIZE - BUTTON_INSET
                ),
              });
            }

            continue;
          }

          if ($isElementNode(child)) {
            visitNode(child);
          }
        }
      };

      visitNode();
    });

    for (const element of Array.from(styledBlocksRef.current.keys())) {
      if (!currentElements.has(element) || !element.isConnected) {
        restoreCodeBlock(element);
      }
    }

    setOverlays(nextOverlays);
  }, [editor, enabled, restoreCodeBlock, styleCodeBlock]);

  const queueSync = useCallback(() => {
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
    }
    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = null;
      syncCodeBlocks();
    });
  }, [syncCodeBlocks]);

  useLayoutEffect(() => {
    if (!enabled) {
      setOverlays([]);
      return;
    }

    const editorRoot = editor.getRootElement();
    const overlayRoot = overlayRootRef.current;
    const positioningRoot = overlayRoot?.parentElement;
    if (!editorRoot || !overlayRoot || !positioningRoot) return;

    const unregisterMutationListener = editor.registerMutationListener(
      CodeNode,
      queueSync,
      { skipInitialization: false }
    );
    const unregisterUpdateListener = editor.registerUpdateListener(queueSync);

    const observer = new MutationObserver(syncCodeBlocks);
    observer.observe(editorRoot, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    const resizeObserver = new ResizeObserver(queueSync);
    resizeObserver.observe(editorRoot);
    resizeObserver.observe(positioningRoot);

    window.addEventListener('resize', queueSync);
    queueSync();

    return () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
      unregisterMutationListener();
      unregisterUpdateListener();
      observer.disconnect();
      resizeObserver.disconnect();
      window.removeEventListener('resize', queueSync);
      for (const element of Array.from(styledBlocksRef.current.keys())) {
        restoreCodeBlock(element);
      }
    };
  }, [editor, enabled, queueSync, restoreCodeBlock]);

  if (!enabled) return null;

  return (
    <div
      ref={overlayRootRef}
      className="pointer-events-none absolute inset-0 z-10"
      aria-hidden={overlays.length === 0}
    >
      {overlays.map((overlay) => (
        <div
          key={overlay.key}
          className="pointer-events-auto absolute"
          style={{ top: overlay.top, left: overlay.left }}
        >
          <CodeBlockCopyButton text={overlay.text} />
        </div>
      ))}
    </div>
  );
}
