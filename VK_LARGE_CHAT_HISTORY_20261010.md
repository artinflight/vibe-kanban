## Later checkpoint: Staging candidate ready; alternate build not released

The Staging reader handles a further approximately 90 MiB native event that this
alternate 64 MiB event limit does not cover. Its tested artifact is the release
candidate. Its real copied-data receipt passed160 checks with eight additional
intact histories/nine authentic finals and the original18 preserved. No live
publication is claimed by this workspace.

The alternate B-backed build's utility tests passed, but server library tests
failed their checkout-local debug-storage assertion under acceptance profile.
No alternate server-build step or release succeeded. Preserve these outputs;
do not relaunch this competing builder. The latest operator notice requires
checkpoint/end and holding new starts for Staging's quiet publication.

# Large-log conversation history repair — October 10 checkpoint

The operator requested that the affected chats work immediately. The latest
steering then requires a safe bounded checkpoint and holding new background
admissions while Staging owns the quiet cutover. This repair is preserved and
validated locally; it is **not deployed**, and live restoration is unverified.

## Source change

Branch `fix/vk-large-chat-history` starts at current `fork/staging` 2693c46d4.
The history reader now has its own 256 MiB capture budget. Review certification
still uses its original 32 MiB limit and unchanged strict review-log reader.
`validate_native_capture` checks outer records and reassembles fragmented native
JSON incrementally, rather than retaining the complete raw file, decoded message
list and concatenated stdout. Raw records are bounded at 16 MiB, native records
at 64 MiB, and record count at one million. Pending writers, unsupported outer
messages, empty stdout, unterminated records and malformed native JSON fail.

The observed affected native events are approximately 31 MiB each, despite outer
pipe records being approximately 5 KiB. The separate native-event bound accounts
for that real evidence; using a 16 MiB native bound would still reject the chats.

## Validation evidence

- Local `cargo test --locked -p utils capture_tests`: seven passed, one explicit
  existing-capture test ignored by default. The large regression uses a 33 MiB
  native JSON event fragmented into 4 KiB stdout chunks; history accepts it while
  both 32 MiB validation and the unchanged review reader reject it.
- Explicit ignored-test invocation passed separately against all five original
  affected captures (a310e7af, b8338039, 00babbe8, 794c1b74, b6643fdb), with one
  test verified to run each time. No captures or capture-state sidecars changed.
- `cargo clippy --locked -p utils --all-targets -- -D warnings`: passed.
- Rust workspace and remote formatting and `git diff --check`: passed.
- Full formatter attempted; frontend formatting remains blocked by missing
  Prettier in this clean worktree. No frontend source changed.

Logs and sanitized native validation results are under mounted secondary
storage `/mnt/vk-storage/vk-weird-error-20261010`. Local compilation uses the
shared SSD Cargo target with incremental compilation disabled.

## Existing builder and hold

Before the quiet-boundary notice, an isolated Desktop B-backed build was started
at `B:/vk-builds/vk-weird-error-20261010/build_large_history_guest.py`. It copies
only the two repaired files onto the exact incumbent source snapshot, preserving
all incumbent recovery/router overlays and frontend behavior. It uses the
existing UID-1000 namespace, network isolation and cached target. It was observed
waiting for the shared builder artifact lock at the checkpoint; no build or
release success is claimed. Preserve the existing process and outputs rather
than launching a duplicate. Inspect `build-result.json` and per-step logs after
it finishes. The local tool session is 73050.

No service, route, configuration, database, native history, review marker,
worker prompt, privilege, queued text or runtime setting was changed. Staging
owns publication; do not introduce a second cutover. Next acceptance must prove
normal finite history API pages and the actual desktop/mobile conversation
render the affected original turns, while review/approval state is preserved.
A successful validator or compiled artifact alone does not prove live recovery.
