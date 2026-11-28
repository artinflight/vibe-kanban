import { $isCodeNode } from '@lexical/code';
import { $createLinkNode, $isLinkNode } from '@lexical/link';
import { TextNode, type LexicalEditor } from 'lexical';

/** Display-only linking: never run in the composer or inside source examples. */
export function registerReadOnlyWebLinks(editor: LexicalEditor): () => void {
  return editor.registerNodeTransform(TextNode, (node) => {
    if (!node.isSimpleText()) return;
    for (let parent = node.getParent(); parent; parent = parent.getParent()) {
      if ($isLinkNode(parent) || $isCodeNode(parent)) return;
    }

    const text = node.getTextContent();
    const match = /(^|[\s(<[{])https?:\/\/[^\s<>"`]+/i.exec(text);
    if (!match) return;
    let url = match[0].slice(match[1].length);
    // Sentence punctuation and enclosing delimiters are not part of the URL.
    // Preserve balanced parentheses in paths, such as Wikipedia article URLs.
    while (url) {
      const last = url.at(-1)!;
      const opening =
        last === ')'
          ? '('
          : last === ']'
            ? '['
            : last === '}'
              ? '{'
              : undefined;
      if (
        /[.,;:!?]/.test(last) ||
        (opening && url.split(last).length > url.split(opening).length)
      ) {
        url = url.slice(0, -1);
      } else break;
    }
    try {
      new URL(url);
    } catch {
      return;
    }
    const start = match.index + match[1].length;
    const end = start + url.length;
    // URL-only inline code is a common summary format. Keep actual code inert.
    if (node.hasFormat('code') && (start !== 0 || end !== text.length)) return;
    const angleWrapped = text[start - 1] === '<' && text[end] === '>';
    const from = angleWrapped ? start - 1 : start;
    const to = angleWrapped ? end + 1 : end;
    const parts = node.splitText(from, to);
    const urlNode = parts[from === 0 ? 0 : 1];
    urlNode.setTextContent(url);
    const link = $createLinkNode(url);
    urlNode.replace(link);
    link.append(urlNode);
  });
}
