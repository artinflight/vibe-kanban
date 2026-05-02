import { useEffect } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import {
  $getSelection,
  $isRangeSelection,
  $isTextNode,
  $createTextNode,
  KEY_ARROW_RIGHT_COMMAND,
  COMMAND_PRIORITY_NORMAL,
} from 'lexical';

const INLINE_CODE_CURSOR_SPACER = '\u200B';

/**
 * Allows users to exit inline code formatting by pressing:
 * - Right arrow at the end of a code-formatted text node
 * - Backtick (`) at the end of a code-formatted text node
 *
 * Without this plugin, Lexical's selection inherits the format of the
 * anchor text node, so the cursor stays "inside" the code format and
 * subsequent characters are also code-formatted.
 *
 * The fix inserts a zero-width space with no formatting as a cursor
 * target after the code node. The zero-width space is cleaned up on
 * the next markdown export/import cycle.
 *
 * Workaround for upstream issues:
 * - https://github.com/facebook/lexical/issues/5518
 * - https://github.com/facebook/lexical/issues/6781
 */
export function InlineCodeBoundaryPlugin() {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    /** If cursor is at the end of a code-formatted text node, insert a
     *  zero-width space after it with no formatting and move cursor there. */
    function $exitCodeNodeIfAtEnd(): boolean {
      const selection = $getSelection();
      if (!$isRangeSelection(selection) || !selection.isCollapsed()) {
        return false;
      }

      if (!selection.hasFormat('code')) {
        return false;
      }

      const node = selection.anchor.getNode();
      if ($isTextNode(node)) {
        if (
          !node.hasFormat('code') ||
          selection.anchor.offset !== node.getTextContentSize()
        ) {
          return false;
        }

        // If the next sibling is already a non-code text node, just move there
        const next = node.getNextSibling();
        if ($isTextNode(next) && !next.hasFormat('code')) {
          next.select(0, 0);
          return true;
        }

        // Insert a zero-width space as a cursor target outside the code node
        const spacer = $createTextNode(INLINE_CODE_CURSOR_SPACER);
        spacer.setFormat(0);
        node.insertAfter(spacer);
        spacer.select(0, 0);
        return true;
      }

      // Empty inline-code selections have no code-formatted text node yet.
      // Add a plain cursor target so a closing backtick can leave code mode.
      const spacer = $createTextNode(INLINE_CODE_CURSOR_SPACER);
      spacer.setFormat(0);
      selection.insertNodes([spacer]);
      spacer.select(0, 0);
      return true;
    }

    const unregisterArrowRight = editor.registerCommand(
      KEY_ARROW_RIGHT_COMMAND,
      (event) => {
        const handled = $exitCodeNodeIfAtEnd();
        if (handled) {
          event.preventDefault();
        }
        return handled;
      },
      COMMAND_PRIORITY_NORMAL
    );

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== '`' || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }

      editor.update(() => {
        if ($exitCodeNodeIfAtEnd()) {
          event.preventDefault();
          event.stopPropagation();
        }
      });
    }

    // Keep the backtick escape handler attached even if Lexical swaps the
    // contentEditable root during focus/mount transitions. Capture phase lets
    // this run before markdown shortcuts consume the closing backtick.
    const unregisterRootListener = editor.registerRootListener(
      (rootElement, prevRootElement) => {
        prevRootElement?.removeEventListener('keydown', handleKeyDown, true);
        rootElement?.addEventListener('keydown', handleKeyDown, true);
      }
    );

    return () => {
      unregisterArrowRight();
      unregisterRootListener();
    };
  }, [editor]);

  return null;
}
