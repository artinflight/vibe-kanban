import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { usePromptSubmission } from '../../packages/web-core/src/features/workspace-chat/model/hooks/usePromptSubmission';

function Harness() {
  const { submit, isSubmitting } = usePromptSubmission();
  const [calls, setCalls] = useState(0);
  const [failed, setFailed] = useState(false);
  const count = () => setCalls((value) => value + 1);
  const hold = () =>
    new Promise<void>((resolve) => {
      document.getElementById('release')!.onclick = () => resolve();
    });
  return (
    <>
      <output>
        {calls}:{String(isSubmitting)}:{String(failed)}
      </output>
      <button
        onClick={() => {
          // Two entry points in the same event, before React can paint loading.
          void submit(async () => {
            count();
            await hold();
          });
          void submit(async () => {
            count();
          });
        }}
      >
        Concurrent Send and correction
      </button>
      <button
        onClick={() =>
          void submit(async () => {
            count();
          })
        }
      >
        Send
      </button>
      <button
        onClick={() =>
          void submit(async () => {
            count();
            throw new Error('Fixture rejection');
          }).catch(() => setFailed(true))
        }
      >
        Fail
      </button>
      <button id="release">Finish request and draft cleanup</button>
    </>
  );
}
createRoot(document.getElementById('root')!).render(<Harness />);
