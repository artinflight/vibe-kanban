Intent: Restore authentic missing native assistant finals to their original Vibe conversations, not just incident notes.
Branch: fix/e3e1-historical-response-recovery
Base: accepted joint604285afbe9a8889aeff2c6a681bd3df998d3770.
Code SHA: pending final hosted acceptance; current00e2a6e8 includes recovery/API/UI/tests.
Changed: dedicated signed recovery API and mode0600 atomic no-clobber response sidecar; exact native session/turn/prompt/revision/hash checks; normal history reader and visible incomplete-capture UI notice; isolated auth/HTTP/restart/identity/damage/race regression suite.
Files: see VK_HISTORICAL_RESPONSE_RECOVERY_20261010.md and git diff604285af.
Commands: cargo fmt --all and git diff --check passed. No local Cargo build. Hosted compiled acceptance pending.
Decisions: preserve raw logs and strict review safeguards; no synthetic writer closure, DB state, badge eligibility, task replay or new credentials. Use existing signed paired client. Unsigned writes denied.
Resume: inspect hosted historical-response-recovery and normal PR CI, repair only scoped failures, export exact patch/source hashes and safe request artifacts to Staging. Staging owns next-restart integration/publication; no production restart authorized.
Dependencies: matching backend plus frontend for persistent warning; existing dot connector reader/API metadata compatible, no new tool or MCP binary. Live recovery waits for next restart and signed import+normal reader/UI acceptance of the two actual reports.
Known limits: response-only recovery does not rebuild missing intermediate messages, independently prove claims in final, or authorize held actions. PR240 queue/capture fix remains a separate already accepted dependency.
