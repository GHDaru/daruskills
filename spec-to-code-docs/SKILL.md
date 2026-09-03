---
name: spec-to-code-docs
description: Generate a navigable documentation site tracing from business source through specs and deliverables to code — taxonomy, traceability matrix, module pages, roadmap, workflow. Use when a project has specs or requirements and you want a human-navigable product documentation site. Triggers on "document the project", "spec to code", "traceability site", "product site", "organize requirements".
---

# spec-to-code-docs

Generate a navigable documentation site that traces from business source through specs, deliverables, and implementation to code — taxonomy, traceability matrix, module pages, roadmap, workflow, shared shell.

## When to use

After a project has specs (or requirements) and implementation. The skill discovers the project structure, extracts data, and generates a static HTML site in `docs/product-site/`.

## How to use

```bash
python generate.py <project-dir> [--output docs/product-site]
```

The generator:
1. **Discovers** specs (specs/*/spec.md, .specify/, docs/), modules (backend/app/modules/, src/), ADRs (docs/adr/), code structure, tests, endpoints.
2. **Extracts** requirements (RF/RNF), traceability (source → spec → code → test), module metadata, roadmap/cycles, metrics.
3. **Renders** HTML pages using templates (index, modules, traceability, roadmap, workflow, styles.css).

## Output

```
docs/product-site/
├── index.html          ← shell SPA (overview, taxonomy, workflow, ADRs, metrics)
├── modules.html        ← modules as epics with features + acceptance criteria
├── traceability.html   ← requirements with forward/backward chain navigable
├── roadmap.html        ← cycles/iterations with temporal axis
├── styles.css          ← shared design (Linear-grade: Inter, SVG, dark mode)
└── progress.html       ← generation progress
```

## Bar

The quality bar is the PROJETO_ECS product site (gauntlet 6/6 vs Atlassian, GitLab, Linear). The output must be as good: navigable from source to code, clear taxonomy, honest traceability, Linear-grade design.

## Design principles

- **Nomenclatura**: épico ⊃ feature ⊃ story, RF/RNF, artefato, ADR — grouped by category (Produto, Engenharia, Metodologia)
- **Rastreabilidade**: cada requisito linka forward (spec → tela → endpoint → teste) e backward (fonte legada)
- **Workflow**: fases com gates verificáveis, owner, métrica, arestas de falha
- **Design**: styles.css compartilhado, SVG icons, dark mode persistente, Inter tipografia, border-radius 8px, transitions 150ms
