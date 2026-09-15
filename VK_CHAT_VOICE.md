# Voice transport and Retell integration

Companion to [architecture](VK_CHAT_ARCHITECTURE.md) and
[contracts](VK_CHAT_CONTRACTS.md). Provider documentation checked 2026-09-15;
capability claims below are documentation evidence, not a tested integration.

## Boundary

Use a narrow voice-session adapter, not a universal telephony framework. The
shared conversation service consumes user utterances and produces assistant text;
it has no Retell call IDs, SDK objects, voice-agent prompts or provider tool state.
The adapter owns those details. Browser media can flow directly to the voice
provider; canonical text and action records still flow through VK.

Proposed backend `VoiceProvider` operations:

- `capabilities()` and `list_voices()` return catalogue metadata and previews.
- `create_session(conversation_binding, voice, retention_policy)` returns provider
  identity plus expiring browser connection material.
- `ingest_provider_event()` verifies and normalises incoming transcript, lifecycle,
  response-request and interruption events.
- `send_response(response_generation, text_chunk, complete)` streams VK-produced
  speech content; `cancel_response()` stops obsolete output when supported.
- `reconcile_session()` and `end_session()` recover status or end media.

Proposed frontend `VoiceClient` owns connect, mute, end, device selection and
connection status. Provider-specific connection data is an opaque tagged payload
consumed only by its adapter. Capability flags describe transcript revisions,
playback acknowledgements, interruption, voice switching and reconnect. Unsupported
features degrade visibly, not through pretend successful operations.

Normalised inputs include `session.connected`, `utterance.partial`,
`utterance.boundary`, `utterance.revised`, `response.requested`,
`speech.interrupted`, `playback.observed`, `session.ended` and `session.error`.
Every input is correlated to VK voice-session ID/generation and provider event or
segment identity. Speech recognition (STT) and synthesis (TTS) are provider
responsibilities, while VK commits text, resolves targets and applies policy.

## Why Retell custom-model mode

Retell documents browser calls without a phone number, live transcript support
and browser microphone/playback requirements. Its current web guide uses
`RetellClient.createWebCall` with a public key, and captions require an additional
transcript connection. Use that as capability evidence, not as VK's desired
public call-creation authority. [Browser call documentation](https://docs.retellai.com/deploy/web-call).

The server Create Web Call API returns a call ID, expiring browser access token,
transport and ICE connection details; it supports per-call configuration overrides.
Recommend server-authorised creation so VK first binds owner, target, voice and
spend policy. Pin and test a matching SDK/API version supporting that join flow;
do not combine legacy `RetellWebClient` examples with current SDK methods.
[Create Web Call reference](https://docs.retellai.com/api-references/create-web-call).

In custom-model mode Retell opens a WebSocket to VK, supplies live transcript
updates and requests response text. `update_only`, `response_required` and
`reminder_required` have different purposes; a response request is not a new user
instruction. Responses have generation-like `response_id` values, and newer
requests can supersede earlier output. The protocol supports reconnect configuration
and streamed responses, but generated text may never be spoken after an
interruption. Retell favours its managed frameworks for general use; VK needs its
own shared text/voice state and action handling, which justifies this custom path.
[Custom-model protocol](https://docs.retellai.com/api-references/llm-websocket).

Do not build two independently reasoning assistants, one in Retell prompts and
one in VK. Retell's response engine forwards to the same VK coordinator used by
text. In direct mode it forwards to the pinned session dispatcher and presentation
service, not global entity resolution. No provider-side tools can mutate VK.

## End-to-end flow

```text
User presses microphone in global or selected-session conversation
  -> VK authenticates, binds conversation/target, commits voice session
  -> Retell adapter creates browser call; VK stores provider correlation
  -> browser joins media with expiring material; microphone indicator stays visible
  -> Retell custom-model socket sends transcript snapshots
  -> adapter reconciles segments; VK commits a stable user utterance
  -> global coordinator OR direct dispatcher accepts the message
  -> durable action receipts and resulting assistant text enter shared history
  -> adapter speaks the text; playback/interruption updates annotate that message
  -> desktop later reads the same history and continues with typed messages
```

Return a short conversational acknowledgement after durable acceptance if agent
work will take time. It may say the agent has been asked, never that the requested
change succeeded. Do not keep a model request open waiting minutes for coding
completion. Result ingestion later creates a linked answer; during an active call,
queue it for a natural speech boundary. Outside a call it remains readable and may
use the existing notification integration with user preference controls.

## Transcript and interruption semantics

Partial transcription is visible but does not authorise actions. Reconcile full
provider transcript snapshots into stable speaker/segment identities using
provider IDs/word timings where present and an adapter-maintained alignment map
otherwise. Repeated identical words are not a safe deduplication key. Keep provider
snapshot revisions bounded; never append the entire snapshot as another message.

A response request proposes a turn boundary. Commit the unconsumed user segment
as one message only once; silence reminders and repeated requests with the same
input create no new dispatch. Persist `(voice_session, segment, accepted_revision)`
correlation before actions. Material corrections arriving before dispatch replace
an uncommitted proposal; after dispatch they become a visible linked correction
and require deliberate corrective action. Do not edit the text that originally
authorised an action out of the audit record.

For initial action-bearing voice turns use a short configurable endpointing
stability window (start at 500 ms and measure), cancel if speech resumes, and ask
when target names or consequential instructions remain unclear. Transcript
certainty alone never grants permission. Destructive or broad operations use the
same scoped confirmation flow as text; a spoken “yes” binds to the current
unexpired confirmation, not an old conversation topic.

Persist canonical assistant text independently of observed speech. Store planned
text, delivered transcript/offset where supported, and `spoken`, `partial`,
`not_spoken` or `unknown` delivery. Default history shows the response with an
interruption marker and expandable “what was spoken”; do not duplicate it as a
second assistant answer. Do not claim word-perfect playback where the provider
only supplies inferred transcript. An interrupted confirmation question must not
be assumed heard. A barge-in fences response generation and unsent proposals;
it cannot undo instructions already delivered to an agent.

The same user may type during a call. Typed messages join the same sequence; audio
output uses the current conversation generation. Topic changes update focus for
future messages and do not retarget in-flight agent work.

## Reconnect and device behaviour

Maintain separate state machines for VK conversation transport and audio transport.
Either can disconnect without deleting history. Resume VK events from durable
sequence; resume media only if supported and safe. Otherwise end/reconcile the old
call and create a new `voice_sessions` segment attached to the existing conversation.
A new call does not replay previously accepted utterances or already spoken output.

Reconnect snapshots may contain the whole call; segment identity and consumed
revision deduplicate them. Late ended/analyzed webhooks reconcile metadata and
missing transcript evidence only, never execute historical instructions. A server
restart marks in-flight generations interrupted, scans actions and reconciles
calls. If transcript finality cannot be established, offer the recovered text as
an unsent draft instead of acting on it.

Allow one microphone owner per conversation with explicit device takeover. End
and release tracks on user stop, logout or permission revocation. For mobile,
validate HTTPS, browser permission, Bluetooth/headset routing, echo cancellation,
network transitions and screen-lock/background suspension. Do not promise continuous
background/locked-screen calling from browser capability evidence. Foreground
mobile voice plus graceful resume is the initial requirement; native background
calling is a separate platform decision. Tauri microphone permissions require
platform-specific acceptance as well.

## Selectable Irish voice

Store a VK voice preference key and provider mapping, not a universal hardcoded
vendor voice ID. Voice catalogue entries include name, provider, accent label,
preview and availability. Retell exposes accent/preview metadata and supports
adding ElevenLabs community voices. [Voice catalogue](https://docs.retellai.com/api-references/list-voices),
[custom voice support](https://docs.retellai.com/build/conversation-flow/global-setting).

ElevenLabs advertises Irish-accent voices and its library supports accent search.
This makes it a credible initial audition source, not proof of quality for this
user. [Irish voice examples](https://elevenlabs.io/text-to-speech/irish-accent),
[voice-library documentation](https://elevenlabs.io/docs/eleven-creative/voices/voice-library).

Audition natural conversational Irish voices on the actual low-latency synthesis
path, using VK project names, short acknowledgements, long explanations and
interruption recovery. The operator chooses the voice; do not substitute a
caricature or an Irish-language model for Irish-accent English. Confirm rights and
availability for the chosen voice. Start with per-user default plus per-conversation
override. Apply a change on the next media segment unless live switching is
verified. If unavailable, offer another voice and keep text usable; never silently
switch accent. No voice cloning is needed.

## Security and third-party processing

Keep secret API keys server-side. Allowlisted voice/model settings, quotas and
short-lived call credentials prevent arbitrary browser-created billable sessions.
An opaque call ID is correlation, not authentication. Provider callbacks cannot
supply their own conversation or workspace binding.

Retell webhook verification uses the raw request body and signature header, with
timestamp/replay checks and constant-time comparison. Persist deduplication before
acknowledging meaningful callback effects. [Webhook signature specification](https://docs.retellai.com/features/secure-webhook).

Do not assume that webhook signatures authenticate the custom-model WebSocket;
its inspected protocol does not specify that contract. For the initial adapter,
require a per-call high-entropy capability in a server-configured custom-model
URL (bound to call/conversation/generation and short expiry), over WSS, plus lookup
of the expected call. Verify that the pinned provider API supports this URL binding
in the milestone-1 contract spike. If not, use an authenticated ingress gateway
with a validated provider connection-auth mechanism before enabling actions.
Unknown/expired bindings fail closed. Scrub capability URLs from proxy/application
logs and rotate on new calls; reconnect is allowed only for the bound active call.

Expose only this narrow voice ingress through a protected public endpoint if
Retell cannot reach the private VK host. Do not publish the local `/api`, relay
credentials, SSH, filesystem or executor control routes. An external ingress
relay is justified only by reachability/auth requirements; it forwards authenticated
voice events over a restricted channel and stores no canonical conversation.
Provisioning that endpoint is a later deployment decision.

Display first-use disclosure of audio/transcript/model processing, providers and
retention. Recommend local text persistence, raw audio recording off and minimum
provider storage compatible with live transcripts and recovery. Retell exposes
storage and retention settings; verify actual account behaviour, including deletion,
with the pinned integration. Do not assume disabling local recording disables
vendor retention. Review provider regions, subprocessors, training/data-use terms,
account access and export/deletion capability at provisioning. These are operational
checks, not claims of legal compliance. Voice vendors receive utterances and spoken
answers, not the full raw agent history. The VK model receives only authorised,
relevant context. Avoid speaking secrets or detailed private evidence without a
clear request, especially when audio may be overheard.

## Replacement and cost

A replacement adapter must pass the transcript/deduplication, interruption,
reconnect, capability-auth and mixed-input conformance suite before activation.
Changing Retell to Vapi, ElevenLabs realtime or a direct audio stack affects voice
transport/configuration only. Keep old provider bindings for history, map the
user's preferred voice to a newly auditioned equivalent, and start a new media
segment. No migration of conversation, memory, actions or execution ownership.
Do not implement speculative adapters now; define the contract and a fake adapter.

Budget recurring cost as voice minutes × transport/STT/TTS rate, plus supervisor
and presentation input/output tokens, summary refreshes, storage/backup, ingress
hosting/egress and optional concurrency/add-ons. Coding-agent turns triggered by
questions retain their own costs. Custom-model billing must avoid counting both
a managed vendor model and VK's model for the same response.

As a dated illustration, Retell's page lists voice infrastructure at $0.055/minute
and ElevenLabs voices at $0.040/minute: 600 minutes would be $57 for those two
components before model usage, add-ons, taxes or other charges. Confirm currency
and the account quote before enabling spend. This is an estimate, not a budget
commitment. [Retell pricing](https://www.retellai.com/pricing).

Track per-call actuals and monthly estimates, set configurable spend alerts and
hard call-duration/concurrency limits, and terminate abandoned calls after a
configurable idle grace period. Low-cost deterministic acknowledgements and cached
source-grounded summaries reduce repeated model calls. Do not buy a vector store,
telephone number or additional orchestration service for the initial release.
