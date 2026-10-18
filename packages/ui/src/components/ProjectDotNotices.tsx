export type ProjectDotNotice = {
  projectId: string;
  name: string;
  unreadCount: number;
};

/** Project notices are independent rows, never activity assigned to a workspace. */
export function ProjectDotNotices({
  notices,
  onOpen,
}: {
  notices: ProjectDotNotice[];
  onOpen?: (projectId: string) => void;
}) {
  if (!notices.length || !onOpen) return null;
  return (
    <div
      role="group"
      aria-label="Project Dot Chat unread notices"
      className="flex flex-col gap-half px-base"
    >
      {notices.map((notice) => (
        <button
          type="button"
          key={notice.projectId}
          data-project-dot-notice={notice.projectId}
          aria-label={`${notice.name}: ${notice.unreadCount} unread project Dot Chat messages`}
          onClick={() => onOpen(notice.projectId)}
          className="flex w-full min-w-0 flex-col text-left px-base py-half text-normal hover:bg-tertiary focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
          style={{
            minHeight: 44,
            overflowWrap: 'anywhere',
          }}
        >
          <span className="w-full min-w-0 text-sm font-medium">
            {notice.name}
          </span>
          <span className="flex items-center gap-1 text-xs text-low">
            <span>Project · Dot Chat</span>
            <span
              data-project-dot-badge
              className="rounded px-1.5 py-0.5 text-xs font-medium"
              style={{
                color: 'hsl(var(--info, 200 75% 45%))',
                backgroundColor: 'hsl(var(--info, 200 75% 45%) / 0.12)',
              }}
            >
              {notice.unreadCount} unread
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}
