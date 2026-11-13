import {
  memo,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import {
  getCodeLanguages,
  normalizeCodeLanguage,
  PrismTokenizer,
} from '@lexical/code';
import { CODE_HIGHLIGHT_CLASSES } from '../lib/code-highlight-theme';
import { splitDotMessage } from '../lib/dot-code-blocks';

const languages = new Set(getCodeLanguages());
// Keep very large blocks selectable/copyable without blocking chat on tokenizing.
const MAX_HIGHLIGHT_LENGTH = 50_000;
type Token = ReturnType<typeof PrismTokenizer.tokenize>[number];
function tokenView(token: Token | Token[], key: number): ReactNode {
  if (typeof token === 'string') return token;
  if (Array.isArray(token)) return token.map(tokenView);
  return (
    <span key={key} className={CODE_HIGHLIGHT_CLASSES[token.type]}>
      {tokenView(token.content, 0)}
    </span>
  );
}

function CodeBlock({ text, language }: { text: string; language: string }) {
  const [status, setStatus] = useState<
    'idle' | 'copying' | 'copied' | 'failed'
  >('idle');
  const generation = useRef(0);
  useEffect(() => {
    const epoch = generation.current;
    setStatus('idle');
    return () => {
      generation.current = epoch + 1;
    };
  }, [text]);
  useEffect(() => {
    if (status !== 'copied') return;
    const timer = window.setTimeout(() => setStatus('idle'), 1200);
    return () => window.clearTimeout(timer);
  }, [status]);
  const highlighted = useMemo(() => {
    const normalized = normalizeCodeLanguage(language.toLowerCase());
    if (!languages.has(normalized) || text.length > MAX_HIGHLIGHT_LENGTH)
      return text;
    try {
      return PrismTokenizer.tokenize(text, normalized).map(tokenView);
    } catch {
      return text;
    }
  }, [text, language]);
  async function copy() {
    const current = generation.current;
    setStatus('copying');
    try {
      await navigator.clipboard.writeText(text);
      if (current === generation.current) setStatus('copied');
    } catch {
      if (current === generation.current) setStatus('failed');
    }
  }
  return (
    <div className="dot-code-block">
      <div className="dot-code-toolbar">
        <span>{language || 'Plain text'}</span>
        <button
          type="button"
          aria-label="Copy code block"
          disabled={status === 'copying'}
          onClick={() => void copy()}
        >
          {status === 'copied'
            ? 'Copied'
            : status === 'copying'
              ? 'Copying…'
              : 'Copy'}
        </button>
      </div>
      <pre tabIndex={0} aria-label={(language || 'Plain text') + ' code'}>
        <code>{highlighted}</code>
      </pre>
      <span
        role="status"
        className={status === 'failed' ? 'dot-code-copy-error' : 'dot-sr-only'}
      >
        {status === 'copied'
          ? 'Code copied'
          : status === 'failed'
            ? 'Could not copy. Select the code and copy manually, or try Copy again.'
            : ''}
      </span>
    </div>
  );
}

export const DotMessageBody = memo(function DotMessageBody({
  body,
}: {
  body: string;
}) {
  return splitDotMessage(body).map((part) =>
    part.kind === 'code' ? (
      <CodeBlock key={part.offset} text={part.text} language={part.language} />
    ) : (
      <p key={part.offset}>{part.text}</p>
    )
  );
});
