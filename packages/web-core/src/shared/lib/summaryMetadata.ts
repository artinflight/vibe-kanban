import { $isParagraphNode, type LexicalNode } from 'lexical';

const SUMMARY_METADATA_LABELS = [
  'PR',
  'Docs',
  'Churn',
  'Human Needed',
  'Commit/Push',
  'Preview URL',
  'Branch',
  'Worktree',
] as const;
const SUMMARY_METADATA_WITH_COMPLETION = [
  ...SUMMARY_METADATA_LABELS.slice(0, 4),
  'Completion',
  ...SUMMARY_METADATA_LABELS.slice(4),
];
const SUMMARY_METADATA_LABEL_VARIANTS: readonly (readonly string[])[] = [
  [...SUMMARY_METADATA_WITH_COMPLETION, 'Version'],
  SUMMARY_METADATA_WITH_COMPLETION,
  [...SUMMARY_METADATA_LABELS, 'Version'],
  SUMMARY_METADATA_LABELS,
  ['Completion'],
];

function isSummaryMetadataLine(text: string, label: string): boolean {
  return text.trimStart().startsWith(`${label}::`);
}

export function findSummaryMetadataChildren(
  children: LexicalNode[]
): LexicalNode[] {
  for (const labels of SUMMARY_METADATA_LABEL_VARIANTS) {
    const lastChild = children.at(-1);
    const lastChildLines = lastChild?.getTextContent().split('\n') ?? [];
    if (
      $isParagraphNode(lastChild) &&
      lastChildLines.length === labels.length &&
      lastChildLines.every((line, index) =>
        isSummaryMetadataLine(line, labels[index])
      )
    ) {
      return [lastChild];
    }

    const candidates = children.slice(-labels.length);
    if (
      candidates.length === labels.length &&
      candidates.every(
        (node, index) =>
          $isParagraphNode(node) &&
          isSummaryMetadataLine(node.getTextContent(), labels[index])
      )
    ) {
      return candidates;
    }
  }

  return [];
}
