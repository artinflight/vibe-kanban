# Vibe Kanban Preview Guide

Use this guide when an operator asks for a preview of a Vibe Kanban change.
For routine frontend review, start only the branch frontend and connect it to
the existing green backend. Do not start a second Vibe Kanban backend or create
a second database.

## Choose the right preview

### Frontend-only change

Use the lightweight preview for React, CSS, layout, navigation, or copy changes.
It serves the frontend from the current worktree and proxies API and WebSocket
requests to the existing green backend at `127.0.0.1:4511`.

### Backend or migration change

The lightweight preview cannot exercise backend code from the branch because it
still uses the running `4511` backend. If the change adds an API route, changes
Rust behavior, or adds a migration:

1. Use the lightweight preview only to inspect its frontend portion.
2. State clearly that backend behavior is not present in that preview.
3. Use an isolated backend and isolated data directory only when the operator
   asks for backend preview testing.
4. Never point an experimental backend at the live green database.

Do not restart the green backend merely to create a preview. A green restart is
a deployment operation and requires the normal restart safety workflow.

## Start the normal preview

Run these commands from the feature worktree:

```bash
pnpm run preview:light
pnpm run preview:light:status
```

Expected output includes a local frontend URL and this backend:

```text
Preview running: http://127.0.0.1:<preview-port>/
Backend proxy: http://127.0.0.1:4511/
```

The helper records the selected frontend port in `.vk-preview/port`.

## Publish the operator review URL

The dynamically allocated `184xx` Tailscale Serve URL is tailnet-only. Do not
give it to the operator unless they explicitly confirm their browser is on the
tailnet. A browser outside the tailnet will commonly report
`ERR_CONNECTION_TIMED_OUT`.

Publish the running frontend through the approved public Funnel port:

```bash
preview_port="$(cat .vk-preview/port)"
tailscale funnel --bg --https 8443 "http://127.0.0.1:${preview_port}"
```

The operator URL is:

```text
https://mcp-server.tail744c4.ts.net:8443/
```

## Verify before sharing

Do not report the preview as ready until both probes succeed:

```bash
curl -skfI --max-time 10 https://mcp-server.tail744c4.ts.net:8443/
curl -skf --max-time 10 https://mcp-server.tail744c4.ts.net:8443/api/info
```

Confirm all of the following:

- the first probe returns an HTTP success response;
- `/api/info` returns JSON from the green backend;
- the browser shows the feature branch frontend;
- data matches the green instance the operator expects;
- the public URL opens from the operator's browser.

Only then report:

```text
Preview URL:: Updated [Open preview](https://mcp-server.tail744c4.ts.net:8443/)
```

## Troubleshooting

### The URL times out

If the URL uses an `184xx` port, it is probably the tailnet-only Serve route.
Repeat the `tailscale funnel` command for port `8443`, run both probes again,
and share only the `8443` URL.

If the `8443` URL times out, check the preview before changing anything else:

```bash
pnpm run preview:light:status
pnpm run preview:light:logs
preview_port="$(cat .vk-preview/port)"
curl -sfI --max-time 10 "http://127.0.0.1:${preview_port}/"
tailscale funnel status
```

Restart only the lightweight frontend if it stopped. Do not start another
backend as a workaround for a Funnel or Vite failure.

### The preview shows a different database

Stop. The preview is connected to the wrong backend. The normal preview must
report:

```text
Backend proxy: http://127.0.0.1:4511/
```

Stop the incorrect preview and start it again without a backend override:

```bash
pnpm run preview:light:stop
pnpm run preview:light
```

Do not use `pnpm run dev`, `pnpm run dev:qa`, port `4411`, or a new data
directory for routine frontend review.

### The frontend works but a saved value disappears

Check whether the branch changes backend persistence or fallback API routes. A
frontend preview backed by the old `4511` binary cannot demonstrate un-deployed
backend behavior. Report that limitation instead of starting another instance.

## Stop the preview

When review is complete:

```bash
pnpm run preview:light:stop
```

Run only one lightweight preview per worktree and do not leave duplicate Vite,
Cargo watch, or full development processes running.

## Command reference

```bash
pnpm run preview:light          # start in the background
pnpm run preview:light:run      # run attached to a VK preview panel
pnpm run preview:light:status   # show frontend and proxy status
pnpm run preview:light:logs     # inspect Vite output
pnpm run preview:light:stop     # stop this worktree's preview
```

Override `VK_PREVIEW_PORT` only when a fixed frontend port is needed. Override
`VK_PREVIEW_BACKEND_PORT` only when the operator explicitly requests a preview
against a known isolated backend.
