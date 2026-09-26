# Voice transport and Retell integration

Companion to [architecture](VK_CHAT_ARCHITECTURE.md) and
[contracts](VK_CHAT_CONTRACTS.md). Provider documentation checked 2026-09-15;
capability claims below are documentation evidence, not a tested integration.
Android call integration references checked 2026-09-26. Android-first mobile voice
and car MMI call controls supersede the earlier foreground-browser mobile scope.

## Boundary

Use a narrow voice-session adapter, not a universal telephony framework. The
supervisor conversation service consumes utterances and produces conversational
responses. Workspace voice instead sends transcribed input through the existing
agent/session message path and leaves its raw response/history unchanged. Neither
path needs Retell call IDs, SDK objects or provider tool state in its chat model.
The adapter owns those details. Native Android or browser media can flow directly to the voice
provider; canonical text and action records still flow through VK.

Proposed backend `VoiceProvider` operations:

- `capabilities()` and `list_voices()` return catalogue metadata and previews.
- `create_session(binding, voice, retention_policy)` returns provider
  identity plus expiring client connection material for an explicitly supported platform. The binding is either a
  supervisor conversation or an existing workspace/session, never both.
- `ingest_provider_event()` verifies and normalises incoming transcript, lifecycle,
  response-request and interruption events.
- `send_response(response_generation, text_chunk, complete)` streams VK-produced
  speech content; `cancel_response()` stops obsolete output when supported.
- `reconcile_session()` and `end_session()` recover status or end media.

Proposed client `VoiceClient` owns connect, mute, end, device selection and
connection status. Provider-specific connection data is an opaque tagged payload
consumed only by its adapter. Capability flags describe transcript revisions,
playback acknowledgements, interruption, voice switching and reconnect. Unsupported
features degrade visibly, not through pretend successful operations.

Normalised inputs include `session.connected`, `utterance.partial`,
`utterance.boundary`, `utterance.revised`, `response.requested`,
`speech.interrupted`, `playback.observed`, `session.ended` and `session.error`.
Direct mode requires no second reasoning/summarisation agent. Optional TTS reads
the existing coding-agent response (or a user-selected passage) without semantic
rewriting. Mechanical speech formatting and prose selection preserve the meaning of played
passages, mark skipped technical content and never alter the stored response. Playback controls and transport
metadata stay outside the normal workspace transcript.

Every input is correlated to VK voice-session ID/generation and provider event or
segment identity. Speech recognition (STT) and synthesis (TTS) are provider
responsibilities, while VK commits text, resolves targets and applies policy.

## Android client and native call integration

Build a thin native Kotlin Android app, with supervisor calling as the default and
an explicit workspace/session selector for direct voice. VK remains the source of
truth for all conversations and actions. Native captions are views of those same
records; the app does not introduce another assistant, memory store or workspace
conversation. Desktop web retains text/history and later browser voice reuses the
same backend contract. A WebView shell alone is insufficient.

The product requirement is a real platform-integrated VoIP call: the user's car MMI
must show the ongoing call and offer its supported call controls, like the
experience the user reports with ChatGPT voice. That comparison is a UX target,
not evidence about ChatGPT internals or a requirement to copy them. Bluetooth
call audio alone is insufficient without call state/control integration.

Use Jetpack Core-Telecom as the recommended Android integration. Register the app
and add an audio call through `CallsManager`, with `MANAGE_OWN_CALLS` and microphone
permissions. Handle platform lifecycle callbacks, post the required foreground
notification and let Telecom own endpoint routing. Keep the media SDK from fighting
Telecom for audio routes. These are documented platform capabilities; the chosen
SDK must demonstrate compatibility. [Core-Telecom guide](https://developer.android.com/develop/connectivity/telecom/voip-app/telecom).

Telecom supports self-managed calls, Bluetooth head units and automotive call
experiences. Prefer this integration without becoming the default dialler. A
separate Android Auto app, SIM call, Twilio number or phone dial-out is not required
by this design. Validate Bluetooth hands-free and Android Auto separately where
the operator uses them; they are different connection paths. Exact controls and
labels depend on the phone and MMI. [ConnectionService reference](https://developer.android.com/reference/android/telecom/ConnectionService).

Start calls from an explicit visible user action, then maintain the supported
foreground call lifecycle while the screen locks or the app backgrounds. Declare
the service types/permissions required by the selected Android/Telecom versions;
do not assume background microphone startup is allowed. On permission revocation
or platform termination, close media and reconcile backend state.
[Android microphone restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start).

### Native call lifecycle and acceptance

- Use a stable local call handle mapped to the VK binding and current media
  generation. Platform active/disconnected state follows actual media readiness.
- Car/headset hang-up stops capture and playback immediately, releases the platform
  call and idempotently ends the VK/provider voice session. It does not stop an
  already-running coding task or erase its history. Offline end is reconciled; a
  bounded server lease/idle timeout prevents an orphan billable call.
- Reflect mute and endpoint changes in both UI and media. Support hold/inactive
  transitions only when media can actually suspend; do not advertise unsupported
  capabilities. Telecom arbitration for another call must suspend/end VK audio
  appropriately, with no microphone leakage into the competing call.
- Network recovery never resends accepted instructions. Retain the platform call
  only during a bounded recoverable media interruption; otherwise disconnect and
  offer explicit resume. A late reconnect must not resurrect a call after hang-up.
- Test on the operator's phone and car: MMI shows a call, car microphone/speakers
  work, MMI/steering-wheel hang-up ends it, supported mute controls agree, locked
  screen sustains conversation, an incoming cellular call is handled, and network
  loss/recovery leaves no duplicate instruction or ghost call. Record phone/OS,
  MMI model/software and Bluetooth versus Android Auto mode. Emulator or handset
  speaker success alone cannot close car acceptance.

## Why Retell custom-model mode

Retell remains the initial provider candidate, conditional on a supported native
Android media path that works with Telecom. No native Retell SDK compatibility has
been established by this design. The early spike must prove server-authorised
joining, audio routing, lifecycle control and custom-model transcript delivery on
Android; browser SDK documentation is insufficient. If that gate fails, record the
blocker and choose a supported provider adapter without changing VK conversation
ownership or settling for a WebView workaround.

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
supervisor text. In direct mode the adapter uses the existing pinned session's
message path and optionally streams its raw response to TTS. It does not invoke
the supervisor model, summarisation, memory or entity resolution. A custom-model
protocol endpoint here is an adapter, not an additional model. No provider-side
tools can mutate VK.

## End-to-end flow

```text
User starts Android supervisor/direct call (or later browser microphone)
  -> VK authenticates, binds supervisor conversation OR session, commits voice metadata
  -> provider adapter creates authorised media session; VK stores correlation
  -> Android registers Telecom call and joins supported native media transport
       (browser surface uses its browser adapter)
  -> call/microphone controls stay available through the platform notification/MMI
  -> provider adapter (Retell custom-model socket when selected) sends transcripts
  -> adapter reconciles segments and accepts stable input once
  -> supervisor: its coordinator/history -> conversational response -> speech
  -> workspace: existing session message path -> raw agent response/history
       -> optional raw-response TTS, with separate playback metadata
  -> desktop later reads the appropriate unchanged history owner and types there
```

In the supervisor, return a short conversational acknowledgement after durable
acceptance if agent
work will take time. It may say the agent has been asked, never that the requested
change succeeded. Do not keep a model request open waiting minutes for coding
completion. Result ingestion later creates a linked answer; during an active call,
queue it for a natural speech boundary. Outside a call it remains readable and may
use the existing notification integration with user preference controls.

For workspace voice, show delivery through existing session controls. Any spoken
transport acknowledgement is deterministic and separate from agent history. The
agent response remains the normal detailed workspace response; there is no
conversation-result ingestion or summary step in that path.

## Speech content: natural plain English

The global supervisor produces speech-ready plain-English prose. Its normal
spoken channel never recites bullet/numbered lists, test-count inventories, commit
hashes, paths, code blocks, JSON, URLs or opaque IDs. It explains what happened,
what matters and what needs the user, with length appropriate to the question.
Meaningful numbers (for example a requested duration) remain possible in ordinary
sentences; this is not a ban on conveying quantities. Exact technical material is
available visually through raw-evidence links, accompanied by a conversational
explanation. Do not turn a request to show source into code dictation.

Prefer one speech-ready supervisor answer reused for text and speech, with
technical evidence rendered separately as attachments/activity. When an answer
needs a separate speech variant, generate it within the existing supervisor run,
link it to the canonical message and retain the planned/spoken distinction. Never
invent a second voice reasoning agent. Prompt for the listener's understanding
and desired outcome; enforce output structure in code. If structured/code output
leaks into speech, hold it from TTS and use a bounded same-run correction or a
short deterministic explanation that details are available on screen. A regex
cannot assess meaning or replace semantic evaluation.

Direct workspace voice still stores the unmodified coding-agent response. Its
optional playback defaults to prose-only passages; deterministically skip code,
tables, enumerations and opaque technical tokens with a visible skipped-content
indicator. Preserve the exact original and provide selection/stop controls. This
is a playback filter, not a paraphrase or supervisor round trip. If the available
output is entirely technical or cannot safely be filtered, keep it on screen and
use a short transport notice rather than reciting it or silently changing meaning.
Do not claim prose from a coding agent has been conversationally rewritten.

Exercise these rules using text fixtures before live voice setup. The same approved
text samples then become TTS audition and car-audio acceptance inputs. Natural
speech must still disclose material failures and uncertainty; brevity must not
hide them. The implementation plan defines the early acceptance gate.

## Transcript and interruption semantics

Partial transcription is visible but does not authorise actions. Reconcile full
provider transcript snapshots into stable speaker/segment identities using
provider IDs/word timings where present and an adapter-maintained alignment map
otherwise. Repeated identical words are not a safe deduplication key. Keep provider
snapshot revisions bounded; never append the entire snapshot as another message.

A response request proposes a turn boundary. Commit the unconsumed user segment
once into the supervisor conversation or existing session message path; silence
reminders and repeated requests with the same
input create no new dispatch. Persist `(voice_session, segment, accepted_revision)`
correlation before actions. Material corrections arriving before dispatch replace
uncommitted input; after dispatch they require deliberate corrective input via
the same interface. Supervisor corrections link to their original message; direct
corrections use existing session messaging and keep revision metadata in voice
storage. Do not edit the text that originally
authorised an action out of the audit record.

For initial action-bearing voice turns use a short configurable endpointing
stability window (start at 500 ms and measure), cancel if speech resumes, and ask
when supervisor targets or consequential instructions remain unclear. In direct
mode the selected session is fixed; unclear transcription stays a draft for user
correction, without a reasoning agent. Transcript certainty alone never grants
permission. Supervisor destructive/broad operations use its text confirmation
flow; workspace voice retains existing session permissions and approval
controls; a spoken “yes” binds to the current
unexpired confirmation, not an old conversation topic.

In supervisor mode, persist canonical assistant text independently of observed
speech. Store planned
text, delivered transcript/offset where supported, and `spoken`, `partial`,
`not_spoken` or `unknown` delivery. Default history shows the response with an
interruption marker and expandable “what was spoken”; do not duplicate it as a
second assistant answer. Do not claim word-perfect playback where the provider
only supplies inferred transcript. An interrupted confirmation question must not
be assumed heard. A barge-in fences response generation and unsent proposals;
it cannot undo instructions already delivered to an agent. In direct mode, retain
only transport revisions and playback references separately; do not annotate or
replace normal workspace response history. Barge-in stops direct audio playback,
not the coding-agent execution. New speech follows existing session send semantics.

The same user may type during a call. Supervisor text joins its conversation
sequence and topic focus. Workspace text and transcribed input both use existing
session ordering; no supervisor sequence or topic resolution applies. Changing a
workspace voice target requires an explicit session binding change, never inference
from the spoken topic. In-flight agent work keeps its original target.

## Reconnect and device behaviour

Maintain separate state machines for VK conversation transport and audio transport.
Either can disconnect without deleting history. Resume supervisor events from its
durable sequence; workspace chat uses its existing history/reconnect path. Resume
media only if supported and safe. Otherwise end/reconcile the old call and create
a new `voice_sessions` segment with the same supervisor or existing-session binding.
A new call does not replay previously accepted utterances or already spoken output.

Reconnect snapshots may contain the whole call; segment identity and consumed
revision deduplicate them. Late ended/analyzed webhooks reconcile metadata and
missing transcript evidence only, never execute historical instructions. A server
restart marks in-flight generations interrupted, scans actions and reconciles
calls. If transcript finality cannot be established, offer the recovered text as
an unsent draft instead of acting on it.

Allow one microphone owner per supervisor conversation or existing session
binding with explicit device takeover. Fence and disconnect the previous native
call as well as its provider media before activating another microphone owner.
End and release capture on user stop, logout or permission revocation. Android
screen-off calling and car controls follow the acceptance gate above. Browser
voice remains a secondary surface: validate HTTPS, microphone permission and
foreground/reload recovery without promising browser background calling. Tauri
microphone permissions require platform-specific acceptance as well.

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
availability for the chosen voice. Start with per-user default plus
per-supervisor-conversation or voice-session
override. These are voice settings, not supervisor memory applied to workspace
chat. Apply a change on the next media segment unless live switching is
verified. If unavailable, offer another voice and keep text usable; never silently
switch accent. No voice cloning is needed.

## Security and third-party processing

Keep secret API keys server-side. Allowlisted voice/model settings, quotas and
short-lived call credentials prevent arbitrary client-created billable sessions.
Use authenticated/protected VK access from Android (including the existing tailnet
path where configured), with revocable app credentials protected by Android
Keystore when credentials are needed. Do not embed provider keys in the APK.
Use a generic call label such as “VK Supervisor” by default so car/lock-screen
displays do not expose project names; show a direct target in the app.
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
A mobile replacement must also pass native Telecom/media and real car acceptance;
a browser-only replacement cannot claim equivalent Android support.
Changing Retell to Vapi, ElevenLabs realtime or a direct audio stack affects voice
transport/configuration only. Keep old provider bindings for history, map the
user's preferred voice to a newly auditioned equivalent, and start a new media
segment. No migration of conversation, memory, actions or execution ownership.
Do not implement speculative adapters now; define the contract and a fake adapter.

Budget recurring cost as voice minutes × transport/STT/TTS rate, plus supervisor
input/output tokens, summary refreshes, storage/backup, ingress
hosting/egress and optional concurrency/add-ons. Native VoIP does not add PSTN
minutes; APK signing/distribution, Android compatibility and device/car regression
work are additional maintenance costs. Coding-agent turns triggered by
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
source-grounded supervisor summaries reduce repeated model calls. Direct workspace
voice incurs STT/TTS/transport and normal coding-agent costs, with no second
reasoning or summarisation model. Do not buy a vector store,
telephone number or additional orchestration service for the initial release.
