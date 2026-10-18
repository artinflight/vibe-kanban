# T63 deployment pickup retained during Staging reconciliation

These dated additions remain historical evidence; the full rollout record is
[VK_PROJECT_COLLABORATION_ROLLOUT.md](VK_PROJECT_COLLABORATION_ROLLOUT.md).

## STATE.md — exact local additions and edits

```diff
--- merge-base/STATE.md
+++ T63/STATE.md
@@ -1,3 +1,14 @@
+# Project sidebar — live October 17
+
+Seamus-authorized project collaboration is live: Dot 11:38:35 UTC, frontend 11:39:12 UTC.
+Read VK_PROJECT_COLLABORATION_ROLLOUT.md. Source 4ecaa2f81 is tree-equivalent to
+staging merge 4ba47fe66; exact-source CI is fully green. Actual served project
+and legacy Dot UI/API acceptance passes at 393/1440 px, with QA cleanup and zero
+wake attempts. All real messages/access/subscriptions and live CU1.6 pins are
+preserved. Dot-only readiness 1.012 s; Vibe/backend/agents/static/gateway unchanged.
+App version remains 0.1.42. Both Desktop backup/restore chains are verified.
+Earlier preparation notes below are historical and do not describe current status.
+
 # Project collaboration sidebar — October 17 preparation
 
 The local Projects sidebar is prepared on its feature branch, not deployed.
```

## STREAM.md — exact local additions and edits

```diff
--- merge-base/STREAM.md
+++ T63/STREAM.md
@@ -1,3 +1,13 @@
+# Project sidebar deployment — October 17
+
+Seamus's "deploy it" authorized scoped Dot service/connector and combined frontend
+activation. PR267 merged into staging 4ba47fe66; build 4ecaa2f81 has the identical
+full source tree and completely passing CI. Deployed and accepted against actual
+served UI/live API at 393/1440 px. No Rust backend restart or PR264 activation.
+See VK_PROJECT_COLLABORATION_ROLLOUT.md for exact assets, timing, preservation,
+Desktop recovery and remaining platform/physical-phone acceptance limits.
+Earlier feature-preparation boundaries below are superseded by this deployment.
+
 # Project collaboration sidebar — October 17
 
 Branch `vk/7db7-vk-project-dot-c` starts at fork/staging `7110930b6`.
```

## HANDOFF.md — exact local additions and edits

```diff
--- merge-base/HANDOFF.md
+++ T63/HANDOFF.md
@@ -1,4 +1,19 @@
-# Project sidebar pickup — October 17
+# Project sidebar deployed — October 17
+
+Project collaboration is LIVE. Read VK_PROJECT_COLLABORATION_ROLLOUT.md.
+Dot readiness 1.012 s at 11:38:35 UTC; frontend 11:39:12 UTC. New entry index-DpbIoqaC.js,
+CSS index-C9c5vx_3.css, API 0.1.42. Runtime root:
+`/mnt/vk-storage/vk-project-sidebar-rollout-20261017`.
+[PR267](https://github.com/artinflight/vibe-kanban/pull/267) is merged; build 4ecaa2f81
+is tree-equivalent to staging 4ba47fe66; CI is fully green. Both actual served
+project/legacy Dot phone+desktop suites pass. CU/Stop pins, real pairing,
+subscriptions and messages retained; QA owners/data cleaned, zero wake attempts.
+Vibe PID 3927146 and all non-Dot services/agents unchanged. Verified Desktop before,
+boundary and after recovery material is under B:/vk-backups/vk-project-sidebar-rollout-20261017/.
+Future Staging frontend candidates must retain this sidebar with Mobile, Steering,
+Dot attention and artifact viewer. No real-owner browser session was inspected.
+
+# Historical project sidebar preparation — October 17
 
 [Draft PR267](https://github.com/artinflight/vibe-kanban/pull/267) is pushed; implementation `f60c8d1d6b2c`.
 [Open sidebar preview](https://vibe.local/vk-artifact-viewer.html?id=15bb5759-3ce8-4234-9081-7c524f4ac8e5&name=project-sidebar-review.html&v=1). Both viewport cases and the
```
