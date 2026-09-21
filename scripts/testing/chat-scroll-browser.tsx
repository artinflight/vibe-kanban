import React, { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { useConversationVirtualizer } from "../../packages/web-core/src/features/workspace-chat/model/useConversationVirtualizer";

import { useResumeConversationAtBottom } from "../../packages/web-core/src/features/workspace-chat/model/useResumeConversationAtBottom";

function Harness() {
  const contentContainerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(4000);
  const { scrollToBottom } = useConversationVirtualizer({
    rows: [],
    contentVersion: height,
    totalRowCount: 1,
    scrollContainerRef,
    contentContainerRef,
  });
  const [scope, setScope] = useState("first");
  useResumeConversationAtBottom(scope, () => scrollToBottom("auto"));
  return (
    <>
      <button onClick={() => setScope((value) => value + "next")}>
        Switch chat
      </button>
      <button onClick={() => setHeight((value) => value + 1000)}>Grow</button>
      <button onClick={() => scrollToBottom("auto")}>Resume</button>
      <div
        ref={scrollContainerRef}
        id="chat"
        style={{ height: 400, overflow: "auto" }}
      >
        <div ref={contentContainerRef} style={{ height }}>
          Conversation
        </div>
      </div>
    </>
  );
}
createRoot(document.getElementById("root")!).render(<Harness />);
