import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";
import { renderToStaticMarkup } from "../../packages/ui/node_modules/react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useApprovalMutation } from "../../packages/web-core/src/features/workspace-chat/model/hooks/useApprovalMutation";
import { ChatApprovalCard } from "../../packages/ui/src/components/ChatApprovalCard";
import { calls } from "./mcp-approval-ui-api";

test("the real approval UI hook emits consent only after explicit actions", async () => {
  let controls: ReturnType<typeof useApprovalMutation> | undefined;
  function Fixture() {
    controls = useApprovalMutation();
    return (
      <ChatApprovalCard
        title="codex.mcp_approval"
        content="Allow run_session_prompt for the synthetic Reporting session? Approve this call only."
        expanded
        status={{ status: "pending_approval" }}
        renderMarkdown={({ content }) => <p>{content}</p>}
      />
    );
  }
  const queryClient = new QueryClient();
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <Fixture />
    </QueryClientProvider>,
  );
  assert.match(html, /run_session_prompt.*synthetic Reporting/);
  assert.match(html, /Approve this call only/);
  assert.equal(calls.length, 0);
  const request = {
    approvalId: "synthetic-approval",
    executionProcessId: "00000000-0000-4000-8000-000000000001",
  };
  await controls!.approveAsync(request);
  await controls!.denyAsync({
    ...request,
    reason: "synthetic explicit decline",
  });
  assert.deepEqual(
    calls.map((call) => call.response),
    [
      {
        execution_process_id: request.executionProcessId,
        status: { status: "approved" },
      },
      {
        execution_process_id: request.executionProcessId,
        status: { status: "denied", reason: "synthetic explicit decline" },
      },
    ],
  );
  assert.ok(calls.every((call) => call.id === request.approvalId));
  writeFileSync(
    resolve(process.env.VK_TEST_OUTPUT!, "mcp-ui-responses.json"),
    JSON.stringify(calls.map((call) => call.response)),
  );
  queryClient.clear();
});
