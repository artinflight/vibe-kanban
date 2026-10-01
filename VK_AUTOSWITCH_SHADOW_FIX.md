# TF::Build Shadow continuity repair

## Temporary no-restart activation (October 1)

The operator authorized fresh genuine model checks and the browser-only fix.
Frontend commit `8d4b9ead2` is live; backend PID1504649 is unchanged. All nine
previously verified model/effort pairs were retested once, with no retries.
Proof expires October2 at16:10:26 UTC under the still-running backend’s original
24-hour rule. TF::Build now has a Shadow follow-up draft. Desktop/mobile browser
checks confirm reload persistence and unchanged Sol6.1/xhigh selection. No task
was submitted. Reload the page before continuing ordinary Shadow work.

The permanent backend refresh code described below remains undeployed.
Activation evidence and verified rollback copies are in
`/mnt/vk-storage/vk-model-autoswitch-20260930/no-restart`.
The following delivery-boundary paragraph records the earlier development pass.

## Observed failure (October 1, 2026)

TF::Build execution `96b68847-44f1-4498-90da-780153404667` began at
14:28 UTC with Shadow enabled. Its native availability proof expired at 13:58.
The persisted decision classified protected work but reported
`recommendation_unavailable`; Sol6.1/xhigh actually ran. Delegation could not
initialize. Later requests omitted routing configuration. This was not a complete
Shadow acceptance. Native interruption is a separate lifecycle observation, not
proof of a model-quality failure or a cause attributed to this router defect.
Sanitized inspection evidence is under
`/mnt/vk-storage/vk-model-autoswitch-20260930/v2-shadow-tf-build-20261001`.

## Repair

- Chat routing consent now falls back to the latest execution in **this session**
  when a draft is cleared or the view remounts. Current operator choices and saved
  draft settings still win. New sessions never inherit routing from another chat.
  This repairs the UI hydration path; it does not retroactively opt existing manual
  executions into Shadow or infer whether an operator intended a historical change.
- Availability discovery keeps its 24-hour TTL. On expiry, one bounded native
  `initialize`, `account/read`, and paginated `model/list` sequence renews it.
  There is no thread/turn creation, paid inference or background scheduler.
- Historical successful execution of an exact model/effort remains valid when a
  fresh catalog confirms support on the same launcher, canonical home, native
  runtime identity and account. Original `verified_at` and `verified_efforts`
  remain unchanged. New catalog entries do not become execution-verified.
- Undiscovered models and legacy proofs without runtime identity retain the
  recent-execution requirement. An expired legacy proof needs explicit verification.
  Changed runtime/account, missing evidence, unsupported effort, future timestamps,
  exclusions and unqualified combinations still block automatic selection.
- Parent routing, semantic classification and child routing use the same proof
  rule. Native account/model/effort checks and CU `vk.routing.v1` are unchanged.
- Refresh has a 15-second shared RPC deadline, 16-page/2-MiB output bounds,
  process-group cleanup, one concurrent attempt and a 60-second failure cooldown.
  Existing Codex disable/capacity guards apply. A file lock and atomic replacement
  protect the proof; failed refresh preserves the previous file and reports a
  warning/unavailable decision. Auto fails closed; Shadow preserves manual execution.
  Successful refresh logs elapsed time and does not claim new verification usage.

## Delivery boundary

Developed on `fix/autoswitch-shadow-continuity` from current `fork/staging`.
Version remains 0.1.42. No production file, profile, service, active task or phone
state is changed by this development pass. The native metadata test uses a private
copy of the exact production proof and its launcher/account/home; it spends no
inference tokens. Full live Shadow acceptance remains pending after normal release
adoption. TF::Build's later manual executions require an explicit Shadow selection
because silently reenabling routing would override human control.

Validation results and artifact paths are recorded in HANDOFF.md.
