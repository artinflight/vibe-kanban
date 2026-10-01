# AutoSwitch V2 staging integration

The operator authorized a PR, push and rebase merge into `staging` on October 1.
This integrates the full V2 source. It does not deploy, activate Auto, or perform
the still-pending complete live Shadow test. Version remains 0.1.42.

## Scope and preservation

Base: `198d55a20ca6bc65a091ee1cc5aa884488ca0027`. The seven V2 commits were rebased with
`--onto fork/staging 9b334d1a3`; V1's already-merged commits were excluded.
The original source is preserved at `preserve/autoswitch-v2-before-staging-20261001`
(`ec94e7f494b6de544fc7bb52ac35e266103a3b09`) and in the prior verified ZIP.

| Original | Rebased |
| --- | --- |
| `64e9cb5bd` | `860b9d975` |
| `b55d1585b` | `ae0505633` |
| `078aa1bc1` | `3951644fa` |
| `d0097776c` | `aeffddd01` |
| `dbabb21ce` | `4f58e524e` |
| `42dacc224` | `eec0fa08e` |
| `ec94e7f49` | `6f8272f1f` |

Only `DELTA.md`, `HANDOFF.md` and `STREAM.md` conflicted. Both V2 history and
staging's V1/preparation notes were retained. Range-diff confirms unchanged source
patches. Newer staging capacity/goal-resume code and deployment tools are preserved.

Included: automatic task envelopes and configurable qualified model/effort pairs;
bounded repo-aware deterministic triage and cheap structured semantic fallback;
manual floors/locks/exclusions; boundary escalation; controlled delegated children,
focused context and fan-out/duplicate controls; capacity counting correction;
confirmed next-turn model updates; classification/delegation usage attribution.
CU `vk.routing.v1` remains byte-compatible; hierarchy and classifier feeds are additive.

## Validation boundary

Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/v2-staging`.
The prior bounded native child acceptance remains valid: exact runtime model/effort,
same-thread escalation, native/CU identity and dirty-state preservation passed.
No inference path was changed in conflict resolution, so it was not rerun.
The broader V2 live Shadow test and empirical net-savings measurement remain pending.

The generic local workspace commands include the unchanged Tauri desktop shell,
whose GTK development libraries are absent on this host. CI explicitly excludes
`vibe-kanban-tauri` from normal backend tests/Clippy. Those equivalent backend
checks are used here; frontend checks use CI's 8 GiB Node heap setting.
Final local and PR CI results are recorded in the PR and integration evidence.

No staging/deployment agent was contacted, no service restarted, no production
configuration changed, and no deployment workflow was started. The operator owns
all actions after merge. Use a fresh ordinary chat and current launcher/account/home
proof for the separately handled complete V2 Shadow validation.
