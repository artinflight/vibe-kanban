import type { ReactNode } from "react";
import { splitGoalCheckpoint } from "../lib/goalCheckpoint";

export interface ChatAssistantMessageRenderProps {
  content: string;
  workspaceId?: string;
}

interface ChatAssistantMessageProps {
  content: string;
  workspaceId?: string;
  renderMarkdown: (props: ChatAssistantMessageRenderProps) => ReactNode;
}

export function ChatAssistantMessage({
  content,
  workspaceId,
  renderMarkdown,
}: ChatAssistantMessageProps) {
  const message = splitGoalCheckpoint(content);
  const checkpoint = message.checkpoint;
  if (!checkpoint) return renderMarkdown({ content, workspaceId });

  return (
    <div className="space-y-base">
      {message.content &&
        renderMarkdown({ content: message.content, workspaceId })}
      <section
        aria-label="Goal checkpoint"
        className="rounded border border-border bg-panel p-base text-base text-normal space-y-base break-words"
      >
        <div className="flex flex-wrap items-center gap-base">
          <span className="font-medium text-high">Goal checkpoint</span>
          <span
            className={
              checkpoint.disposition === "complete"
                ? "text-success"
                : "text-low"
            }
          >
            {checkpoint.disposition === "needs_input"
              ? "Needs your input"
              : checkpoint.disposition === "complete"
                ? "Completed"
                : "Continuing"}
          </span>
        </div>
        {checkpoint.reason && (
          <p className="whitespace-pre-wrap">{checkpoint.reason}</p>
        )}
        {[
          { label: "Requirements", entries: checkpoint.requirements },
          { label: "Verified this checkpoint", entries: checkpoint.completed },
        ].map(
          ({ label, entries }) =>
            Object.keys(entries).length > 0 && (
              <details key={label}>
                <summary className="cursor-pointer text-low">
                  {label} ({Object.keys(entries).length})
                </summary>
                <dl className="mt-base space-y-base">
                  {Object.entries(entries).map(([id, description]) => (
                    <div key={id}>
                      <dt className="font-medium">{id}</dt>
                      <dd className="whitespace-pre-wrap">{description}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            ),
        )}
        {checkpoint.recovery_plan && (
          <details>
            <summary className="cursor-pointer text-low">Recovery plan</summary>
            <p className="mt-base whitespace-pre-wrap">
              {checkpoint.recovery_plan}
            </p>
          </details>
        )}
      </section>
    </div>
  );
}
