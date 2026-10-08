import { useEffect, useRef, useState } from 'react';
import type { ApprovalInfo } from 'shared/types';
import { ChatApprovalCard } from '@vibe/ui/components/ChatApprovalCard';
import { PrimaryButton } from '@vibe/ui/components/PrimaryButton';
import { useApprovalMutation } from '../model/hooks/useApprovalMutation';

export const MCP_CONSENT_TOOL = 'codex.mcp_approval';

/** The composer presents every consent request with its own immutable binding.
 * Snapshot order, timeline order, and the generic composer's implicit selection
 * cannot retarget these controls. Context arrives atomically with the snapshot.
 */
export function McpConsentCards({
  approvals,
  executionProcessIds,
  isConnected,
}: {
  approvals: ApprovalInfo[];
  executionProcessIds: string[];
  isConnected: boolean;
}) {
  return (
    <div className="flex flex-col gap-base">
      {approvals
        .filter(
          (info) =>
            info.tool_name === MCP_CONSENT_TOOL &&
            executionProcessIds.includes(info.execution_process_id)
        )
        .sort(
          (a, b) =>
            a.created_at.localeCompare(b.created_at) ||
            a.approval_id.localeCompare(b.approval_id)
        )
        .map((info) => (
          <McpConsentCard
            key={`${info.execution_process_id}:${info.approval_id}`}
            info={info}
            isConnected={isConnected}
          />
        ))}
    </div>
  );
}

function McpConsentCard({
  info,
  isConnected,
}: {
  info: ApprovalInfo;
  isConnected: boolean;
}) {
  const { approveAsync, denyAsync } = useApprovalMutation();
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitted = useRef(false);
  const mounted = useRef(true);
  const ready =
    isConnected &&
    Boolean(info.mcp_consent?.trim()) &&
    Date.parse(info.timeout_at) > Date.now();
  const current = useRef({ ready, info, isConnected });
  current.current = { ready, info, isConnected };
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function respond(approved: boolean) {
    const { ready, info, isConnected } = current.current;
    if (
      !mounted.current ||
      !isConnected ||
      (approved && !ready) ||
      Date.parse(info.timeout_at) <= Date.now() ||
      submitted.current
    )
      return;
    submitted.current = true;
    setAttempted(true);
    const binding = {
      approvalId: info.approval_id,
      executionProcessId: info.execution_process_id,
    };
    try {
      if (approved) await approveAsync(binding);
      else await denyAsync(binding);
    } catch {
      // An uncertain submission must not silently replay consent.
      setError('Consent could not be confirmed. Refresh the pending requests.');
    }
  }

  return (
    <section
      data-approval-id={info.approval_id}
      data-execution-id={info.execution_process_id}
      aria-label="MCP tool consent"
    >
      <ChatApprovalCard
        title="MCP tool — approve once"
        content={info.mcp_consent ?? 'Waiting for complete action context.'}
        expanded
        status={{ status: 'pending_approval' }}
        renderMarkdown={({ content }) => (
          // Never interpret connector-supplied text as Markdown/HTML/links.
          <pre className="whitespace-pre-wrap break-words text-sm">
            {content}
          </pre>
        )}
      />
      <div className="flex gap-base pt-base">
        <PrimaryButton
          onClick={() => void respond(true)}
          disabled={!ready || attempted}
        >
          Approve this call only
        </PrimaryButton>
        <PrimaryButton
          onClick={() => void respond(false)}
          disabled={!isConnected || attempted}
        >
          Decline this call
        </PrimaryButton>
      </div>
      {!isConnected && (
        <p>Disconnected. Waiting for current pending requests.</p>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
