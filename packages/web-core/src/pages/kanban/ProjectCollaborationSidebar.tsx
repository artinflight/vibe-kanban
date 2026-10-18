import { useCallback, useEffect, useRef, useState } from 'react';
import { useProjectContext } from '@/shared/hooks/useProjectContext';
import { useOrgContext } from '@/shared/hooks/useOrgContext';
import { useAppNavigation } from '@/shared/hooks/useAppNavigation';
import {
  DotSidechatLive,
  PairingRequired,
  dotApi,
  type Session,
} from '../workspaces/DotSidechatLive';
import { DotActivityIndicators } from '@vibe/ui/components/DotActivityIndicators';
import {
  useDotProjectNotifications,
  useDotNotifications,
  useDotWorkspaceNotifications,
} from '@/shared/hooks/useDotNotifications';
import { workspaceDotNotification } from '@/shared/lib/dotWorkspaceActivity';
import './project-collaboration.css';

export type PlanningEntry = {
  id: string;
  revision: number;
  kind: 'checklist' | 'milestone' | 'decision' | 'question';
  title: string;
  body: string;
  issue_ids: string[];
  resolved: boolean;
  target_date: string | null;
};
const sections = {
  checklist: 'Checklist',
  milestone: 'Milestones',
  decision: 'Decisions',
  question: 'Open questions',
} as const;

export function ProjectCollaborationSidebar({
  projectId,
  projectName,
  workspaceId,
  issueId,
  onClose,
  onNavigate,
}: {
  projectId: string;
  projectName: string;
  workspaceId?: string | null;
  issueId?: string | null;
  onClose: () => void;
  onNavigate: (action: () => void) => void;
}) {
  const [tab, setTab] = useState<'chat' | 'plan'>('chat');
  const notifications = useDotProjectNotifications();
  const issues = useDotNotifications();
  const workspaces = useDotWorkspaceNotifications();
  const activity = workspaceId
    ? workspaceDotNotification(
        issueId ?? null,
        issues.find((item) => item.issue_id === issueId),
        workspaces.find((item) => item.workspace_id === workspaceId)
      )
    : notifications.find((item) => item.project_id === projectId);
  return (
    <aside
      className="project-collaboration bg-secondary text-normal"
      aria-label="Project collaboration"
    >
      <header className="project-collaboration-heading">
        <div>
          <strong>{projectName}</strong>
          <span>
            {workspaceId
              ? 'Workspace chat · ' + workspaceId
              : 'Project chat · Seamus & dot'}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close project sidebar"
        >
          ×
        </button>
      </header>
      <div
        className="project-collaboration-tabs"
        role="tablist"
        aria-label="Project space"
      >
        <button
          id="project-chat-tab"
          role="tab"
          aria-selected={tab === 'chat'}
          aria-controls="project-chat-panel"
          onClick={() => setTab('chat')}
        >
          Dot Chat{' '}
          <DotActivityIndicators
            dotUnreadCount={activity?.unread_count ?? 0}
            dotNeedsAttentionCount={activity?.needs_attention_count ?? 0}
          />
        </button>
        <button
          id="project-plan-tab"
          role="tab"
          aria-selected={tab === 'plan'}
          aria-controls="project-plan-panel"
          onClick={() => setTab('plan')}
        >
          Shared plan
        </button>
      </div>
      <div
        id="project-chat-panel"
        role="tabpanel"
        aria-labelledby="project-chat-tab"
        hidden={tab !== 'chat'}
        className="project-chat-slot"
      >
        <DotSidechatLive {...(workspaceId ? { workspaceId } : { projectId })} />
      </div>
      {tab === 'plan' && (
        <div
          id="project-plan-panel"
          role="tabpanel"
          aria-labelledby="project-plan-tab"
          className="project-plan-slot"
        >
          <ProjectPlan
            key={projectId}
            projectId={projectId}
            onNavigate={onNavigate}
          />
        </div>
      )}
    </aside>
  );
}

function ProjectPlan({
  projectId,
  onNavigate,
}: {
  projectId: string;
  onNavigate: (action: () => void) => void;
}) {
  const {
    issues,
    getIssue,
    getStatus,
    getAssigneesForIssue,
    getWorkspacesForIssue,
  } = useProjectContext();
  const { membersWithProfilesById } = useOrgContext();
  const navigation = useAppNavigation();
  const [entries, setEntries] = useState<PlanningEntry[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState<PlanningEntry | null>(null);
  const [saving, setSaving] = useState(false);
  const pending = useRef<{
    project: string;
    request: string;
    entry: PlanningEntry;
  } | null>(null);
  const controller = useRef(new AbortController());
  const busy = useRef(false);
  const refresh = useCallback(async () => {
    try {
      const signal = controller.current.signal;
      const paired: Session = await dotApi('session', signal);
      const data: { entries: PlanningEntry[] } = await dotApi(
        'project-plan?project=' + encodeURIComponent(projectId),
        signal
      );
      if (!signal.aborted) {
        setSession(paired);
        setEntries(data.entries);
        if (!pending.current) setError(null);
      }
    } catch (failure) {
      if (
        failure instanceof PairingRequired &&
        !controller.current.signal.aborted
      ) {
        setSession(null);
        setEntries([]);
        setEditor(null);
        pending.current = null;
      }
      if (!controller.current.signal.aborted)
        setError(
          (failure as Error).message +
            ' Open Dot Chat to pair this browser if needed.'
        );
    } finally {
      if (!controller.current.signal.aborted) setLoading(false);
    }
  }, [projectId]);
  useEffect(() => {
    const lifetime = new AbortController();
    controller.current = lifetime;
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh();
    }, 5000);
    return () => {
      lifetime.abort();
      window.clearInterval(timer);
    };
  }, [refresh]);

  const storageKey = session
    ? 'vibe-project-plan-pending:' + session.session_id + ':' + projectId
    : null;
  useEffect(() => {
    if (!storageKey) return;
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const retained = JSON.parse(saved) as NonNullable<
          typeof pending.current
        >;
        if (
          retained.project === projectId &&
          retained.request &&
          retained.entry?.id
        ) {
          pending.current = retained;
          setEditor(retained.entry);
        }
      }
    } catch {
      setError(
        'This browser cannot retain an uncertain plan edit across reloads. Enable tab storage before saving.'
      );
    }
  }, [storageKey, projectId]);

  async function save(entry: PlanningEntry) {
    if (!session || !storageKey || busy.current) return;
    busy.current = true;
    setSaving(true);
    try {
      pending.current ??= {
        project: projectId,
        request: crypto.randomUUID(),
        entry: {
          id: entry.id,
          revision: entry.revision,
          kind: entry.kind,
          title: entry.title,
          body: entry.body,
          issue_ids: entry.issue_ids,
          resolved: entry.resolved,
          target_date: entry.target_date,
        },
      };
      sessionStorage.setItem(storageKey, JSON.stringify(pending.current));
      await dotApi(
        'project-entry',
        controller.current.signal,
        pending.current,
        session.csrf
      );
      sessionStorage.removeItem(storageKey);
      pending.current = null;
      setEditor(null);
      await refresh();
    } catch (failure) {
      if (
        failure instanceof PairingRequired &&
        !controller.current.signal.aborted
      ) {
        setSession(null);
        setEntries([]);
        setEditor(null);
        pending.current = null;
      }
      if (!controller.current.signal.aborted)
        setError(
          (failure as Error).message +
            ' Your edit is retained. Retry the same save, or refresh and review the latest entry.'
        );
    } finally {
      busy.current = false;
      setSaving(false);
    }
  }
  function start(kind: PlanningEntry['kind']) {
    pending.current = null;
    setEditor({
      id: crypto.randomUUID(),
      revision: 0,
      kind,
      title: '',
      body: '',
      issue_ids: [],
      resolved: false,
      target_date: null,
    });
  }
  function taskLinks(entry: PlanningEntry) {
    return entry.issue_ids.map((id) => {
      const issue = getIssue(id);
      if (!issue)
        return (
          <p key={id} className="text-low">
            Linked task unavailable · {id.slice(0, 8)}
          </p>
        );
      const owners = getAssigneesForIssue(id).map((assignment) => {
        const member = membersWithProfilesById.get(assignment.user_id);
        return member?.first_name ?? member?.username ?? 'Assigned owner';
      });
      return (
        <div key={id} className="project-task-link">
          <button
            type="button"
            onClick={() =>
              onNavigate(() => navigation.goToProjectIssue(projectId, id))
            }
          >
            {issue.simple_id} · {issue.title}
          </button>
          <span>
            {getStatus(issue.status_id)?.name ?? 'Loading status'} ·{' '}
            {owners.join(', ') || 'Unassigned'}
          </span>
          {getWorkspacesForIssue(id)
            .filter((workspace) => workspace.local_workspace_id)
            .map((workspace) => (
              <button
                type="button"
                key={workspace.id}
                onClick={() =>
                  onNavigate(() =>
                    navigation.goToProjectIssueWorkspace(
                      projectId,
                      id,
                      workspace.local_workspace_id!
                    )
                  )
                }
              >
                ↗ {workspace.name || 'Workspace'}
              </button>
            ))}
        </div>
      );
    });
  }
  return (
    <section className="project-plan" aria-label="Shared project plan">
      <p className="text-low">
        Checklists, milestones and decisions shared with dot. Linked task status
        and owners stay in Vibe.
      </p>
      {loading && <p role="status">Loading shared plan…</p>}
      {error && (
        <div role="alert">
          {error}
          <button type="button" onClick={() => void refresh()}>
            Refresh plan
          </button>
        </div>
      )}
      {editor && (
        <form
          className="project-entry-editor"
          onSubmit={(event) => {
            event.preventDefault();
            void save(editor);
          }}
        >
          <strong>
            {editor.revision ? 'Edit' : 'Add'}{' '}
            {sections[editor.kind].toLowerCase()}
          </strong>
          <fieldset disabled={saving || pending.current !== null}>
            <label>
              Title
              <input
                autoFocus
                maxLength={240}
                required
                value={editor.title}
                onChange={(e) =>
                  setEditor({ ...editor, title: e.target.value })
                }
              />
            </label>
            <label>
              Notes
              <textarea
                aria-label="Notes"
                maxLength={10000}
                rows={3}
                value={editor.body}
                onChange={(e) => setEditor({ ...editor, body: e.target.value })}
              />
            </label>
            {editor.kind === 'milestone' && (
              <label>
                Target date
                <input
                  type="date"
                  value={editor.target_date ?? ''}
                  onChange={(e) =>
                    setEditor({
                      ...editor,
                      target_date: e.target.value || null,
                    })
                  }
                />
              </label>
            )}
            <label>
              Link Vibe tasks
              <select
                aria-label="Link Vibe tasks"
                multiple
                value={editor.issue_ids}
                onChange={(e) =>
                  setEditor({
                    ...editor,
                    resolved: false,
                    issue_ids: Array.from(
                      e.target.selectedOptions,
                      (option) => option.value
                    ),
                  })
                }
              >
                {issues.map((issue) => (
                  <option key={issue.id} value={issue.id}>
                    {issue.simple_id} · {issue.title}
                  </option>
                ))}
              </select>
            </label>
            {!!editor.issue_ids.length && (
              <button
                type="button"
                onClick={() => setEditor({ ...editor, issue_ids: [] })}
              >
                Clear task links
              </button>
            )}
            <label className="project-entry-resolution">
              <input
                type="checkbox"
                checked={editor.resolved}
                disabled={
                  !!editor.issue_ids.length &&
                  (editor.kind === 'checklist' || editor.kind === 'milestone')
                }
                onChange={(e) =>
                  setEditor({ ...editor, resolved: e.target.checked })
                }
              />
              {editor.kind === 'decision'
                ? 'Decision recorded'
                : editor.kind === 'question'
                  ? 'Question resolved'
                  : 'Complete (unlinked items only)'}
            </label>
          </fieldset>
          <div>
            <button type="submit" disabled={saving || !editor.title.trim()}>
              {saving
                ? 'Saving…'
                : pending.current
                  ? 'Retry same save'
                  : 'Save entry'}
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => {
                if (storageKey) sessionStorage.removeItem(storageKey);
                pending.current = null;
                setError(null);
                setEditor(null);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      {Object.entries(sections).map(([kind, label]) => (
        <section key={kind} aria-label={label} className="project-plan-section">
          <header>
            <h3>{label}</h3>
            <button
              type="button"
              disabled={!session || saving || !!editor}
              onClick={() => start(kind as PlanningEntry['kind'])}
            >
              Add {kind === 'checklist' ? 'item' : kind}
            </button>
          </header>
          {!entries.some((entry) => entry.kind === kind) && (
            <p className="text-low">No {label.toLowerCase()} yet.</p>
          )}
          {entries
            .filter((entry) => entry.kind === kind)
            .map((entry) => {
              const linked =
                entry.issue_ids.length > 0 &&
                (kind === 'checklist' || kind === 'milestone');
              const completed = linked
                ? entry.issue_ids.every((id) => {
                    const issue = getIssue(id);
                    return (
                      !!issue &&
                      (!!issue.completed_at ||
                        getStatus(issue.status_id)?.name.toLowerCase() ===
                          'done')
                    );
                  })
                : entry.resolved;
              return (
                <article key={entry.id} className="project-plan-entry">
                  <div>
                    <strong>{entry.title}</strong>
                    <span className="text-low">
                      {completed
                        ? kind === 'decision'
                          ? 'Recorded'
                          : kind === 'question'
                            ? 'Resolved'
                            : 'Complete'
                        : kind === 'question'
                          ? 'Open'
                          : kind === 'decision'
                            ? 'Proposed'
                            : 'In progress'}
                      {linked ? ' · From linked tasks' : ''}
                    </span>
                  </div>
                  {entry.body && <p>{entry.body}</p>}
                  {entry.target_date && <p>Target: {entry.target_date}</p>}
                  {taskLinks(entry)}
                  <button
                    type="button"
                    disabled={saving || !!editor}
                    onClick={() => {
                      pending.current = null;
                      setEditor(entry);
                    }}
                  >
                    Edit {entry.title}
                  </button>
                </article>
              );
            })}
        </section>
      ))}
    </section>
  );
}
