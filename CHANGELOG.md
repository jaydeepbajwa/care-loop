# Changelog

All notable changes to CareLoop are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.1] — 2026-07-03

### Fixed
- JSON `Content-Type` header was silently dropped from every browser request
  (spread-order bug in the fetch wrapper), which made FastAPI reject all form
  submissions with an opaque 422. Found by a real user walking the enrollment
  flow; now covered by a regression test.
- The insurance question required *changing* the dropdown to count as answered —
  it now starts on a "Choose one…" placeholder so any deliberate choice works.
- FastAPI validation errors (list-shaped `detail`) are now formatted into
  readable field-level messages instead of "Request failed (422)".
- Client-side email validation matches the server's (dotted domain required),
  so the Finish button being enabled means the submit will succeed.

## [0.1.0] — 2026-07-03

### Added
- Resumable member enrollment flow (eligibility → consent → contact preferences)
  with per-step autosave and an append-only funnel event table
  (started → eligible → consented → enrolled).
- Sub-60-second symptom check-in (five 0–3 symptom scales + optional free text).
- Two-layer triage: deterministic flagging rules plus Claude-drafted severity and
  suggested next step — surfaced to a human who must accept or override, never
  auto-acted. Every suggestion and decision is written to an audit log.
- Care-team console: flagged queue, member roster, and enrollment funnel report.
- Observability: structured JSON logs (Datadog-ingestible shape), per-route request
  latency metrics at `/metrics`, and a DB-probing `/health` endpoint.
- One-command demo (`docker compose up`) with seeded synthetic data.
- CI: ruff + pytest (API), vue-tsc + vitest + build (web).
