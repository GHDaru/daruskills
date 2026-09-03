# gestaodeprioridades — Inventory

## What it is
Task prioritization app using extended GUT matrix. First federated application for GHDaru platform. APH pattern Level 2.

## Specs (speckit format)
- 001-fundacao-documental (Aprovada) — RF1-RF7, constitution, ADRs, CLAUDE.md
- 002-prototipo-de-interfaces (Aprovada) — RF1-RF12, ux-design, journeys, prototype
- 003-roadmap-e-rounds (Rascunho) — RF1-RF11, rounds, manifesto.json

Spec artifacts: spec.md, plan.md, tasks.md, qa-report.md, retro.md, ux-design.md, contracts/

## ADRs: 19 (0001-0019) in docs/adr/
Key: 0002 stack, 0003 federated, 0005 prototype disposable, 0014 scope P2, 0018 deploy Vercel+Railway

## Skills: 6 (constitution-check, verifiable-dod, fight-the-pile-up, anti-patterns, diagnose-before-fix, living-journey)

## Journeys: 6 (docs/jornadas/001-006) with 21 PNG screenshots

## Scripts: 20 (scripts/) — 12+ CI fitness functions, Python+Node+Bash

## Prototype: prototipo/ (disposable HTML/JS, no framework)

## Source code: NONE yet (pre-implementation). Planned: apps/api/ (FastAPI) + apps/web/ (React)

## Stack: React / FastAPI / PostgreSQL Neon / S3 (Backblaze B2) / OpenTelemetry

## Requirements: EARS syntax (WHEN <condition> THE SYSTEM SHALL <behavior>), RF prefix

## Governance: Maestro (I-VIII, English) + Constitution (P1-P7, Portuguese). docs/governance/

## Key paths
- CLAUDE.md, AGENTS.md
- specs/001-003/
- docs/adr/0001-0019.md
- docs/governance/principles.md, constitution.md, operating-model.md
- docs/produto/visao.md, rounds.md
- docs/jornadas/001-006/ + capturas/
- prototipo/ (index.html, app.js, temas.css)
- scripts/ (20 scripts)
- skills/ (6 skills)
- .specify/ (speckit tooling)
