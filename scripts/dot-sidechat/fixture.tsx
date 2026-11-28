import React from "react";
import { createRoot } from "react-dom/client";
import { DotSidechatFixture } from "../../packages/web-core/src/pages/workspaces/DotSidechatFixture";
import { ResizableSidePane } from "../../packages/ui/src/components/ResizableSidePane";
import "./fixture.css";

createRoot(document.getElementById("root")!).render(
  <main className="fixture-shell">
    <nav className="fixture-rail">
      <b>V</b>
      <span>VK</span>
      <span>⌘</span>
    </nav>
    <section className="fixture-center">
      <header>
        <span>VK / DOT SIDEBAR</span>
        <span className="fixture-badge">ISOLATED PREVIEW</span>
      </header>
      <div className="fixture-intro">
        <p className="eyebrow">A separate space for coordination</p>
        <h1>
          Keep the work moving.
          <br />
          Keep the conversation.
        </h1>
        <p>
          Issue decisions live with the issue. Workspace context travels with
          each message.
        </p>
        <div className="fixture-agent">
          <span className="fixture-status" />
          Coding agent <small>Not connected in this preview</small>
          <p>Your sidechat never sends instructions here automatically.</p>
        </div>
        <div className="fixture-guide">
          <b>Try it</b>
          <p>
            Write a message in the panel. Open Fixture controls to distinguish
            webhook acceptance from a persisted reply. Refresh to verify history
            survives.
          </p>
          <p>Drag the divider, or focus it and use the arrow keys.</p>
        </div>
      </div>
      <footer>
        One private issue thread · complete retained history · no live services
      </footer>
    </section>
    <ResizableSidePane>
      <div className="fixture-details">
        <details className="fixture-section">
          <summary>
            Git <span>prototype/dot-sidechat</span>
          </summary>
          <p>Isolated worktree. Production unchanged.</p>
        </details>
        <details className="fixture-section">
          <summary>Terminal</summary>
          <p>No agent process attached.</p>
        </details>
        <details className="fixture-section">
          <summary>Notes</summary>
          <p>Notes remain separate from the conversation.</p>
        </details>
        <DotSidechatFixture />
      </div>
    </ResizableSidePane>
  </main>,
);
