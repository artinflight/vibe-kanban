# Preview Delivery

## Purpose

This document defines the standard preview workflow for this Vibe Kanban fork when the operator asks an agent to "spin up a preview" or provide a preview link.

## Rule

If the operator asks for a preview, the agent should:

1. start the relevant preview path
2. verify the exact resulting URL
3. return that working link in the final completion message as:
   - `Preview URL:: Updated [Open preview](https://...)`

A localhost-only URL is not enough when the operator needs a remotely openable review link.

## Current Standard Path

This repo does not currently have a dedicated one-command preview deployment flow like `hyroxready-app`.

The standard reviewable preview path today is the Tailscale-backed workflow documented in [`mobile-testing.md`](../../mobile-testing.md):

- Tailscale provides the stable DNS name
- Caddy terminates HTTPS and proxies traffic
- the preview link the operator can open is:
  - `https://$TS_HOSTNAME:3001`

Relay-dependent features should use:

- app/API base: `https://$TS_HOSTNAME:3001`
- relay base: `https://$TS_HOSTNAME:8443`

## What Agents Should Do

### For remote-web or phone-review requests

Use the Tailscale flow from `mobile-testing.md` and return the final app URL:

- Docker mode:
  - run the remote stack with `PUBLIC_BASE_URL=https://$TS_HOSTNAME:3001`
  - run Caddy with the generated `Caddyfile`
  - report `https://$TS_HOSTNAME:3001`
- Dev mode:
  - run the remote backends
  - run the Vite dev server for `@vibe/remote-web`
  - run Caddy with `Caddyfile.dev`
  - report `https://$TS_HOSTNAME:3001`

### For local desktop-app flows

If the request is only for a local debug preview and the operator explicitly accepts local-only access, say that clearly and report it as local-only context instead of pretending it is a remote review link.

## Verification Expectation

Before reporting the preview URL:

- verify the relevant processes started successfully
- verify the URL you are returning is the actual Tailscale-hosted URL
- if applicable, verify that the phone or remote client path uses the same hostname and ports documented in `mobile-testing.md`

## Final Message Requirement

When a preview was requested:

- use `Preview URL:: Updated [Open preview](https://...)` if you produced a fresh working link
- use `Preview URL:: NotUpdated [Open preview](https://...)` if an existing working preview remained valid and you intentionally reused it
- use `Preview URL:: Not Generated` only if the preview could not be produced, and explain the blocker in the narrative sections

## Known Gap

This repo still lacks a dedicated preview helper script that wraps the Tailscale workflow and prints the final URL automatically.

Until that exists, agents should follow the documented runbook rather than improvising a different preview path.
