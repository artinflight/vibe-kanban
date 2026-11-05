/** Explicit management metadata, independent of all unread/attention state. */
export function DotManagedIndicator({ managed }: { managed?: boolean }) {
  if (managed !== true) return null;
  return (
    <span
      data-dot-managed
      aria-label="Dot managed"
      title="Explicitly managed by Dot"
      className="inline-flex shrink-0 items-center rounded border border-border px-1.5 py-0.5 text-xs text-normal"
    >
      Dot managed
    </span>
  );
}
