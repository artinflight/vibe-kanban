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
          className="flex min-h-11 w-full min-w-0 flex-col items-start gap-1 rounded border px-base py-half text-left text-normal focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
          style={{
            borderColor: 'hsl(var(--info, 200 75% 45%) / 0.7)',
            backgroundColor: 'hsl(var(--info, 200 75% 45%) / 0.12)',
            borderLeftWidth: 3,
            overflowWrap: 'anywhere',
          }}
        >
          <span className="text-sm font-medium">Project · Dot Chat</span>
          <span className="w-full min-w-0 text-base font-medium">
            {notice.name}
          </span>
          <span className="text-sm">{notice.unreadCount} unread</span>
        </button>
      ))}
    </div>
  );
}
