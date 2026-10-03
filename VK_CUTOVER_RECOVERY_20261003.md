# October 3 Cutover Recovery

## Outcome

The cutover did not succeed. The previous version is available for normal work.
The original Green process3059021 serves5411/5412 through gateway4720 and
https://vibe.local. The candidate Blue production service on5461 never started.
CodexUsage restarted as3921554, and the coordinated temporary writers resumed.
No older database was restored. The same original maintenance conversation resumed.

Authoritative attempt:
`/mnt/vk-storage/vk-blue-prepare-20261003/cutover-20261003T231800Z`.
Read status.json, recovery-acceptance.json, live-browser.json and
open-chat-readonly-browser.json. This attempt is consumed. The continuation
explicitly prohibits retrying it. Preserve its approval, failure and recovery records.

## Release Distinction

Git main e53ae4a7e and staging86d1c083a share prepared tree6963ed5d5d with build
9c2e04d72, promoted through merged PR140/141. That release is NOT production.
The running backend remains SHA256 e2120644ec026eee46f987327b2e98a7ea0e2be79f89e6e518cb8493b2612e12,
with the prior attention-corrected frontend /assets/index-Ci1XTFAo.js.
Both releases use application version0.1.42; that version number alone cannot
distinguish deployment success. Production Codex remains0.159.2.

## Failure And Preparation Gap

The controller started23:17:30UTC and returned failure23:19:45UTC. This135-second
controller interval includes preflight/recovery and is not a measured outage.
Its final_capture.py worker exceeded the90-second interruption budget. The log
shows Desktop archive upload had started, but no boundary.json, accepted result
or verified Desktop receipt was completed for that capture. Do not count it as a
successful frozen-boundary backup or advance the verified chain to it.

During online catch-up, the journal correctly rejected newly moved personal-home
Codex daemon/plugin directories. Two explicit whole-subtree recopy roots were
added, preserving kernel-watch/scope/event checks and independent content hashing.
A new daemon-updater.sock also required type-checked handling: only the exact
owned Unix socket warning is allowed; ordinary files, symlinks, unknown warnings
and out-of-scope paths remain errors.52 existing operational tests and the focused
online/fenced socket regression passed. The application binary did not change.

The updated tools were resealed and Desktop-restored, but the enlarged final
capture workload was not remeasured against the90-second deadline. Reusing the
earlier49.31-second rehearsal was insufficient timing evidence for this package.
This was a preparation failure, not evidence that the new application is broken.
The exact bottleneck within Desktop delivery/verification remains unmeasured.
Do not simply raise the timeout or claim a guaranteed minute based on old evidence.

## Preserved Data And Recovery Acceptance

Read-only comparison against this attempt's protected-state.json passed for all
existing project/task/workspace/repository/session/execution/turn/attachment IDs,
saved messages, navigation order, card colors, scratch/model configuration and
repository/attachment relationships. All366 previously present attachment hashes
match. All6056 native thread identities/paths were checked; previously available
rollouts still exist without shrinking. The2282 historical missing-rollout paths
remain historical exceptions, not newly recovered or newly lost data.

Database quick_check passed. All12 saved messages match the pre-switch values.
All13635 pre-switch review flags remain intact; the resumed maintenance turn adds
one journal-explained record, bringing the snapshot to13636. No historical flags
were restored. Public browser tests at1440/390 pixels show the two actual Needs
Attention workspaces: MM::Orchestration Agent and OH::Kevin Coman Podcast Edit.
All review writes were intercepted during browser checks. Opening/foreground
request behavior and background/polling preservation passed without marking real
operator work read. This is UI-request verification, not a fresh live DB mutation
test of review semantics.

Public saved-message settings, seven models, all four reasoning choices and
websocket traffic pass at both sizes with no JavaScript exceptions. Screenshots
were inspected. Mobile is browser emulation, not a physical-phone/network test.
An actual unique attachment upload/download passed; only that test upload was
deleted. All three required attachment roots retain ownership and mode0755.

The resumed execution retains native thread01a03e74-2c1a-72f0-9e00-8e4293fe910d
and its exact manual GPT-6 Astra/high configuration. Live VK/CU process settings
share the private routing feed, and CU imported this turn's decision/binding.
No new error-priority service log entries were found after recovery. Steer/Stop
and native-goal execution evidence remains the earlier isolated candidate fixture;
no additional production agent was launched, stopped or steered during recovery.
This acceptance certifies recovery of the previous version, not deployment of
the candidate or every candidate workflow running in production.

## Verified Backups And Next Step

Latest verified online delta: fae18b06e8744c88aa29be36e49e010f,420931673bytes,
SHA2560887944220027ff6b1dec9199fefe0f31ba27ed18a55231e9430ce5cc9581604,
on Desktop B:/vk-backups/vk-autoswitch-scope-release-20261001 plus the retained
parent chain. Fresh carConsole supplement is separately verified and required.
The pre-interruption review snapshot is Desktop verified with SHA256
3459b33c399af89874e61edfa4676e0dc68d1d5467943d6cb53faf2207b74001.
The resealed software package maintenance-software-20261003T231534Z.tar.zst is
Desktop verified/restored,2485 bound files, SHA256
d3ce73714b17c70d1f5eca9068ba95da69af849218779a76b90a448be1ee3269.

Failed capture882f9feca37941b4be0765b4c0a5c1a9 is uncertified and retained for
diagnosis; latest-result.json still points to the verified online delta.
No further cleanup was performed during this recovery.

Next: diagnose and reduce the final capture cost, rehearse the exact enlarged
workload including Desktop verification in a fresh package, then obtain new
cutover approval. Keep production available throughout preparation. Never replay
this attempt, replace the conversation, reset review flags, or restore an old DB.
