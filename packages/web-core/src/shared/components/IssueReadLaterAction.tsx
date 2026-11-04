import { ReadLaterButton } from '@vibe/ui/components/ReadLaterButton';
import { useReadLater } from '@/shared/hooks/useReadLater';

export function IssueReadLaterAction({
  issueId,
  projectId,
  title,
  unread,
}: {
  issueId: string;
  projectId: string;
  title: string;
  unread: boolean;
}) {
  const { isReadLater, setReadLater } = useReadLater();
  const later = isReadLater('issue', issueId);
  if (!unread && !later) return null;
  return (
    <ReadLaterButton
      later={later}
      onToggle={() =>
        setReadLater(
          { kind: 'issue', id: issueId, projectId, name: title },
          !later
        )
      }
    />
  );
}
