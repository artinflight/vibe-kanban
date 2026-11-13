export function projectDotNotices(
  notifications: { project_id: string; unread_count: number }[],
  projects: { id: string; name: string }[]
) {
  const names = new Map(projects.map((project) => [project.id, project.name]));
  return [
    ...new Map(notifications.map((item) => [item.project_id, item])).values(),
  ]
    .filter(
      (item) => Number.isSafeInteger(item.unread_count) && item.unread_count > 0
    )
    .map((item) => ({
      projectId: item.project_id,
      name: names.get(item.project_id) ?? `Project ${item.project_id}`,
      unreadCount: item.unread_count,
    }));
}

type ProjectChatRequest = { projectId: string; sequence: number };
let request: ProjectChatRequest | null = null;
let sequence = 0;
const listeners = new Set<() => void>();
export const subscribeProjectChatRequest = (notify: () => void) => {
  listeners.add(notify);
  return () => {
    listeners.delete(notify);
  };
};
export const getProjectChatRequest = () => request;
export function consumeProjectChatRequest(value: ProjectChatRequest) {
  if (request !== value) return;
  request = null;
  [...listeners].forEach((notify) => notify());
}
export function openProjectDotChat(
  projectId: string,
  goToProject: (id: string) => void,
  currentProjectScope?: string | null
) {
  request = { projectId, sequence: ++sequence };
  // The route must drop workspace/issue selection before the request is consumed.
  if (currentProjectScope !== projectId) goToProject(projectId);
  [...listeners].forEach((notify) => notify());
}
