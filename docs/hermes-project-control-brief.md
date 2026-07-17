# Hermes Agent Web UI — Project Control Brief

This is the canonical control brief for the existing Site project. Generated
status is updated from `project-control/project-control.json`; project decisions
and protected boundaries outside the marked region remain human-maintained.

## Project identity

- Site slug: `hermes-agent-web-ui`
- Site project ID: `appgprj_6a57ca3238c081919fcc5634802b2800`
- Tracked milestone: Version 25
- Revision key: `hermes-site-version-25-905ac4e9d18b`
- Adapter phase: `host-synchronized`
- Last synchronized: `2026-07-16T21:23:19.524Z`
- Visual direction: graphite-and-cyan
- Layouts: responsive desktop and mobile
- Mobile navigation: preserve all six destinations

## Current control status

<!-- BEGIN GENERATED PROJECT CONTROL STATUS -->
Generated: `2026-07-17T01:40:10.805990Z`

| Control | Value | Status | Evidence |
|---|---|---|---|
| Repository | `MerverliPy/hermes-webui` | recorded | — |
| Generation source revision | `84682b4a1f7b56084174724de62f0897eaf532bb` | verified | git: git rev-parse HEAD |
| Generation branch | `fix/project-control-version-24` | verified | git: git branch --show-current |
| Tracked project version | `Version 25` | verified | ChatGPT Sites host receipt: revision 25; revision key hermes-site-version-25-905ac4e9d18b |
| Site project | `appgprj_6a57ca3238c081919fcc5634802b2800` | verified | ChatGPT Sites host receipt: Hermes Agent Web UI; synchronized 2026-07-16T21:23:19.524Z |
| Authoritative Site checkpoint | `Unresolved` | unresolved | — |
| Authoritative Site deployment | `Unresolved` | unresolved | — |
| Website Control Studio host adapter | `host-synchronized; no direct Sites API or credentials; production publishing unavailable` | verified | host adapter: site identity and revision receipt synchronized at 2026-07-16T21:23:19.524Z |
| Screenshot comparison | `Version 23 production screenshot failed; current reconciliation unresolved` | unresolved | Version 24 handoff: failed Version 23 screenshot preserved; exact failure details unresolved |
| Cancellation recovery | `Hermes live response could not complete; the current conversation is preserved` | failed | — |
<!-- END GENERATED PROJECT CONTROL STATUS -->

## Protected authority boundary

The Version 25 identity and revision receipt are synchronized by the ChatGPT
host. Website Control Studio has no direct Sites API or credentials, and
production publishing is unavailable through the Studio.

## Protected simulation boundary

Do not claim that agents, tasks, missions, models, telemetry, approvals,
settings, artifacts, tools, or persistence are connected to a real Hermes
backend unless independently verified.

## Unresolved product issues

- Authoritative Site checkpoint and deployment IDs: unresolved
- Failed Version 23 production screenshot: preserved; exact failure details unresolved
- Current screenshot reconciliation: unresolved
- Cancellation-recovery gap: unresolved
- Exact observed recovery message:
  `Hermes live response could not complete; the current conversation is preserved`
- Historical Studio failure retained as superseded evidence:
  `401 tunnel_active_organization_required; reauthentication_required`

## Recommended milestone

Harden Studio adapter and mutation safeguards, verify cancellation recovery,
and keep scheduled writeback deferred until the corrective change is reviewed.
