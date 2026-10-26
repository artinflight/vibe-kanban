export type DotMessagePart = {
  kind: 'text' | 'code';
  text: string;
  language: string;
  offset: number;
};

// Only fenced blocks are interpreted. Keep ordinary chat text and every byte
// inside the fences intact (including indentation, CRLF and trailing newlines).
// An unfinished fence extends to EOF, so incoming/updated messages stay useful.
export function splitDotMessage(body: string): DotMessagePart[] {
  const parts: DotMessagePart[] = [];
  let plainStart = 0;
  let fence: {
    marker: string;
    length: number;
    start: number;
    language: string;
  } | null = null;
  for (const line of body.matchAll(/([^\r\n]*)(\r\n|\n|\r|$)/g)) {
    if (!line[0]) continue;
    const offset = line.index!;
    const end = offset + line[0].length;
    if (fence) {
      const close = /^ {0,3}(`+|~+)[ \t]*$/.exec(line[1]);
      if (
        close &&
        close[1][0] === fence.marker &&
        close[1].length >= fence.length
      ) {
        parts.push({
          kind: 'code',
          text: body.slice(fence.start, offset),
          language: fence.language,
          offset: fence.start,
        });
        fence = null;
        plainStart = end;
      }
      continue;
    }
    const open = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line[1]);
    if (!open || (open[1][0] === '`' && open[2].includes('`'))) continue;
    if (offset > plainStart)
      parts.push({
        kind: 'text',
        text: body.slice(plainStart, offset),
        language: '',
        offset: plainStart,
      });
    fence = {
      marker: open[1][0],
      length: open[1].length,
      start: end,
      language: open[2].trim().split(/\s+/, 1)[0],
    };
  }
  if (fence)
    parts.push({
      kind: 'code',
      text: body.slice(fence.start),
      language: fence.language,
      offset: fence.start,
    });
  else if (plainStart < body.length)
    parts.push({
      kind: 'text',
      text: body.slice(plainStart),
      language: '',
      offset: plainStart,
    });
  return parts;
}
