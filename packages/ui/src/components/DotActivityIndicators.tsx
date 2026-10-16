export interface DotActivityState {
  dotUnreadCount?: number;
  dotNeedsAttentionCount?: number;
}

/** Separate from all coding-agent state; both Dot badges can coexist. */
export function DotActivityIndicators({
  dotUnreadCount = 0,
  dotNeedsAttentionCount = 0,
}: DotActivityState) {
  const badge = {
    color: 'hsl(var(--dot-activity, 270 65% 43%))',
    backgroundColor: 'hsl(var(--dot-activity, 270 65% 43%) / 0.12)',
  };
  return (
    <span
      className="inline-flex shrink-0 flex-wrap items-center gap-1"
      data-dot-indicators
    >
      {dotUnreadCount > 0 && (
        <span
          style={badge}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium"
          title="Unread Dot replies"
          aria-label={`Dot unread replies: ${dotUnreadCount}`}
        >
          <span aria-hidden="true">●</span> Dot {dotUnreadCount}
        </span>
      )}
      {dotNeedsAttentionCount > 0 && (
        <span
          style={badge}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium"
          title="Unresolved Dot question or action"
          aria-label={`Dot Needs Attention: ${dotNeedsAttentionCount}`}
        >
          <span aria-hidden="true">◆</span> Dot · Needs Attention{' '}
          {dotNeedsAttentionCount}
        </span>
      )}
    </span>
  );
}
