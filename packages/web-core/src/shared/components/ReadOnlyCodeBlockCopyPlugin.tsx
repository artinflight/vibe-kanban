import { useEffect, useState } from 'react';
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
const BUTTON_OFFSET = 8;

export function ReadOnlyCodeBlockCopyPlugin({
  enabled = true,
}: ReadOnlyCodeBlockCopyPluginProps) {
  const [editor] = useLexicalComposerContext();
  const [codeBlocks, setCodeBlocks] = useState<CodeBlockOverlay[]>([]);

  useEffect(() => {
    if (!enabled) {
      setCodeBlocks([]);
      return;
    }

    let observer: MutationObserver | null = null;
    let animationFrameId: number | null = null;

    const cancelQueuedSync = () => {
      if (animationFrameId == null) return;
      window.cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    };

    const syncCodeBlocks = () => {
      animationFrameId = null;

      const editorRoot = editor.getRootElement();
      const container = editorRoot?.closest('.wysiwyg');
      if (
        !(editorRoot instanceof HTMLElement) ||
        !(container instanceof HTMLElement)
      ) {
        setCodeBlocks([]);
        return;
      }

      const containerRect = container.getBoundingClientRect();
      const nextCodeBlocks: CodeBlockOverlay[] = [];

      editor.getEditorState().read(() => {
        const visitNode = (node: ElementNode | RootNode = $getRoot()) => {
          for (const child of node.getChildren()) {
            if ($isCodeNode(child)) {
              const element = editor.getElementByKey(child.getKey());
              const text = child.getTextContent().replace(/\n$/, '');

              if (element instanceof HTMLElement && text.trim()) {
                const rect = element.getBoundingClientRect();
                nextCodeBlocks.push({
                  key: child.getKey(),
                  text,
                  top: rect.top - containerRect.top + BUTTON_OFFSET,
                  left:
                    rect.right -
                    containerRect.left -
                    BUTTON_SIZE -
                    BUTTON_OFFSET,
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

      setCodeBlocks(nextCodeBlocks);
    };

    const queueSync = () => {
      if (animationFrameId != null) return;
      animationFrameId = window.requestAnimationFrame(syncCodeBlocks);
    };

    const attachObserver = (root: HTMLElement | null) => {
      observer?.disconnect();
      observer = null;

      if (!root) return;

      observer = new MutationObserver(queueSync);
      observer.observe(root, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
      });
    };

    const unregisterMutationListener = editor.registerMutationListener(
      CodeNode,
      queueSync,
      { skipInitialization: false }
    );
    const unregisterUpdateListener = editor.registerUpdateListener(queueSync);
    const unregisterRootListener = editor.registerRootListener((root) => {
      attachObserver(root);
      queueSync();
    });

    attachObserver(editor.getRootElement());
    window.addEventListener('resize', queueSync);
    queueSync();

    return () => {
      cancelQueuedSync();
      unregisterMutationListener();
      unregisterUpdateListener();
      unregisterRootListener();
      observer?.disconnect();
      window.removeEventListener('resize', queueSync);
    };
  }, [editor, enabled]);

  if (!enabled || codeBlocks.length === 0) {
    return null;
  }

  return (
    <div className="pointer-events-none absolute inset-0 z-20">
      {codeBlocks.map((codeBlock) => (
        <CodeBlockCopyButton
          key={codeBlock.key}
          text={codeBlock.text}
          className="absolute"
          style={{
            top: codeBlock.top,
            left: Math.max(BUTTON_OFFSET, codeBlock.left),
          }}
        />
      ))}
    </div>
  );
}
