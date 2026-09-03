---
name: spec-to-code-docs
description: Generate a navigable documentation site that traces a project from business source (AS-IS) through specs and deliverables to code, AND designs the target architecture (TO-BE) with DDD/Hexagonal decomposition, semantic UX objects, and a migration gap analysis. Use when a project needs product documentation, when you want a traceability site (requirement → spec → code → test), when you need to plan a rewrite/decomposition from legacy to modern architecture, or when stakeholders need a navigable view of specs, modules, roadmap, and architecture. Triggers on "document the project", "spec to code", "traceability site", "product site", "organize requirements", "plan rewrite", "decompose monolith", "AS-IS TO-BE analysis", "bounded context design".
---

# spec-to-code-docs

Generate a navigable documentation site that traces a project from business source through specs, deliverables, and implementation to code — AND designs the target architecture (TO-BE) with DDD/Hexagonal decomposition, semantic UX objects, and a migration gap analysis.

The site has two layers:
- **AS-IS**: what the project is today — specs, requirements, code structure, traceability, roadmap.
- **TO-BE**: what the project should become — bounded contexts, aggregate roots, hexagonal layers, semantic UX objects, migration plan.

## When to use

When a project has specs, code, or both, and stakeholders need a human-navigable product documentation site with traceability from source to code and a target architecture plan.

## The bar

The quality bar is the PROJETO_ECS product site (gauntlet 6/6 vs Atlassian, GitLab, Linear). The output must be as good: navigable from source to code, clear taxonomy, honest traceability, Linear-grade design, and a credible TO-BE architecture plan.

---

## Workflow (5 phases)

The skill runs as a 5-phase workflow. Claude (the agent invoking the skill) participates actively in phases 1, 3, and 5 — these are the intelligent phases where Claude's judgment matters. Phases 2 and 4 are script-driven with Claude review.

### FASE 1 — DESCOBERTA (AS-IS)

**Goal:** Discover the project as it exists today. Extract specs, code, ADRs, tests, endpoints, requirements, artifacts.

```bash
python analyze.py <project-dir> --output as_is.json
```

`analyze.py` scans the project and produces `as_is.json` containing:
- Specs (spec.md, plan.md, tasks.md, qa-report.md, retro.md, contracts/)
- Requirements (RF/RNF, EARS syntax)
- ADRs (docs/adr/)
- Code structure (backend/app/modules/, src/, apps/)
- Tests, endpoints, MCP tools
- Skills, scripts, journeys, prototypes
- Stack (extracted from ADRs or code)
- Metrics (counts: specs, RFs, ADRs, endpoints, tests, telas)

**Claude's role:** Review `as_is.json`. Identify gaps — missing sources, requirements without traceability, modules without specs, specs without code. Formulate questions for stakeholders if critical information is missing. Tag findings with confidence (see Confidence Scale below).

### FASE 2 — TAXONOMIA

**Goal:** Build the domain taxonomy — the ubiquitous language terms that structure the project.

```bash
python taxonomy_builder.py as_is.json --output taxonomy.json
```

`taxonomy_builder.py` extracts domain terms from specs, ADRs, and code, and produces `taxonomy.json` containing 15 terms grouped in 3 categories:
- **Produto**: Épico, Feature, Story, Requisito Funcional (RF), Requisito Não-Funcional (RNF), Critério de Aceitação, Roadmap
- **Engenharia**: Módulo (Bounded Context), Spec, Artefato, ADR, Aggregate Root, Port / Adapter
- **Metodologia**: Gauntlet, Jornada

Each term has: `term`, `id`, `cat`, `def` (definition), `map` (mapping to real usage in THIS project), `analogy`.

**Claude's role:** Refine the terms. Validate that `map` fields are project-specific (not generic). If the project uses different terminology (e.g., "cycle" instead of "spec", "principle" instead of "RNF"), adjust the terms to match the project's ubiquitous language. The taxonomy must reflect THIS project's language, not a template.

### FASE 3 — TO-BE DESIGN (the intelligent phase)

**Goal:** Design the target architecture. This is where Claude's judgment matters most — the script produces a draft, Claude refines it into a credible architecture plan.

```bash
python to_be_planner.py as_is.json --output to_be.json
```

`to_be_planner.py` produces a draft `to_be.json` with:
- Bounded contexts (candidate decomposition)
- Aggregate roots per context
- Hexagonal layers (domain / application / infrastructure / api)
- Semantic UX objects (from specs/prototypes)
- Migration gaps (AS-IS → TO-BE delta)

**Claude's role — REFINE the plan:**

1. **Identify bounded contexts.** Group requirements and code into cohesive domains with their own ubiquitous language. A bounded context is a boundary within which a term has one meaning. Look for:
   - Clusters of requirements that share a vocabulary
   - Existing module boundaries (backend/app/modules/, src/features/)
   - Domain events and their handlers
   - Entities that change together (aggregate consistency)

2. **Designate aggregate roots.** For each bounded context, identify the entity that encapsulates invariants and serves as the entry point for all operations. An aggregate root:
   - Enforces business rules (invariants) that must always be true
   - Is the only entry point for modifications within the aggregate
   - References other entities by identity, not by reference
   - Emits domain events when its state changes

3. **Map hexagonal layers.** For each bounded context, define:
   - **Domain** (entities, value objects, domain services, events, repository interfaces — zero framework, no SQLAlchemy/Pydantic imports)
   - **Application** (use cases, ports, DTOs)
   - **Infrastructure** (adapters: SQLAlchemy repositories, ORM models, Pydantic schemas, security)
   - **API** (inbound adapters: FastAPI routers, MCP tools)
   - **UX** (semantic objects — what the user sees and acts on, before components)

4. **Define UX/UI semantic objects.** From specs and prototypes, extract the semantic objects the user interacts with — not components, but the nouns of the interface. A semantic object has:
   - A name (ubiquitous language)
   - A role (what it represents to the user)
   - Fields (what data it shows/captures)
   - Actions (what the user can do with it)
   - `ai_visible` flag (can an AI agent see/act on this object?)

5. **Identify migration gaps.** For each AS-IS element, determine its TO-BE target and the gap between them:
   - What exists today and maps directly (CONFIRMED)
   - What exists today but needs restructuring (INFERRED)
   - What doesn't exist yet and needs to be built (GAP)

**Architecture-alvo (TO-BE) reference:**
- **DDD + Hexagonal + TDD + Linguagem Ubíqua** — see PROJETO_ECS ADR 0004 (the canonical description of this architecture)
- **Constituição do projeto** — see gestaodeprioridades `docs/governance/constitution.md` (P1–P7 principles: fronteira de escrita, federação por contrato, domínio puro, TDD, observabilidade, jornada viva, segredo no servidor)
- **Semantic objects** — see gestaodeprioridades spec 002 (`ux-design.md`, `ActionSpec`, `proposta-de-acao`)
- **Speckit** — see `.specify/` directory for spec-driven development tooling

### FASE 4 — RENDER

**Goal:** Generate the complete static HTML site from the extracted data.

```bash
python render.py as_is.json --output docs/product-site
```

`render.py` merges `as_is.json` + `taxonomy.json` + `to_be.json` and generates:

```
docs/product-site/
├── index.html          ← shell SPA (overview, taxonomy, workflow, ADRs, metrics, architecture card)
├── modules.html        ← modules/specs as epics with features + acceptance criteria
├── traceability.html   ← requirements with forward/backward chain navigable
├── roadmap.html        ← cycles/iterations with temporal axis, deps, gates
├── styles.css          ← shared design (Linear-grade: Inter, SVG, dark mode)
└── progress.html       ← generation progress
```

**Render quality requirements (learned from 9 gauntlet iterations):**
- **Taxonomy**: 15 terms in 3 categories, each with `def` + `map` (project-specific) + `analogy`. Never list raw RFs as taxonomy terms.
- **Modules**: features with semantic names (not formulaic, not EARS fragments). Vision = §1 of each spec (not the spec title). Acceptance criteria = clean Portuguese (not garbled, not generic "Spec Aprovada").
- **Traceability**: each RF has a source citation. Forward chain: spec → tela → endpoint → teste. Honest percentage (count of traced requirements, not always 100%).
- **Roadmap**: dependencies as cycle IDs ("Ciclo 001 → Ciclo 002"), gates as `F0✓ F1✓ F2✓ F3○ F4○ F5○` (green for done, circle for pending). Flow diagram with 6–7 phases, each with gate text.
- **Overview**: cards for "O que é" (product description), "Arquitetura" (stack from ADRs), "Estado" (deploy + metrics).
- **Workflow**: 7 phases (Setup, Inventário, Specs, Plan/Tasks, Construção, Gauntlet, Deploy) with `entrada`, `saida`, `metric`, `fail.to`, `fail.action` per phase.
- **Design**: styles.css shared, SVG icons 16px stroke=currentColor, dark mode via `prefers-color-scheme` + `data-theme`, Inter tipografia, border-radius 8px, transitions 150ms.

**Claude's role:** Review the generated site. Open each HTML file, verify the render quality requirements above are met. If not, fix `render.py` and re-run.

### FASE 5 — REVIEW

**Goal:** Review the generated site for quality and identify what needs human validation.

**Claude's role:**
1. Open each page (`index.html`, `modules.html`, `traceability.html`, `roadmap.html`) and review against the quality bar.
2. Identify where confidence is GAP (needs human validation) — mark these clearly.
3. Identify where the TO-BE plan is INFERRED (Claude's judgment, not confirmed by code/spec) — mark these.
4. Suggest next steps: what specs need to be written, what code needs to be refactored, what stakeholders need to be interviewed.
5. Produce a review summary with: what's CONFIRMED, what's INFERRED, what's GAP, and recommended actions.

---

## Como lidar com diferentes tipos de projeto

### Projeto com specs (spec-driven)
- **AS-IS**: extract from specs (spec.md, plan.md, tasks.md, qa-report.md). Complement with code if implementation exists.
- **TO-BE**: specs already define the target. Validate that code matches specs. If code diverges, flag the gap.
- **Confidence**: high — specs are the source of truth.
- **Example**: PROJETO_ECS (specs 001–015, 8 modules, ADRs 0001–0005)

### Projeto só com código (reverse-engineering)
- **AS-IS**: reverse-engineer from code. Specs are INFERRED from code structure, naming, tests, and comments.
- **TO-BE**: the code IS the AS-IS. The TO-BE plan proposes improvements (decomposition, DDD, hexagonal).
- **Confidence**: medium — specs are inferred, not authored. Mark as INFERRED.
- **Claude's role**: read the code, infer the domain model, propose bounded contexts based on actual code boundaries.

### Projeto sem código nem specs (greenfield/workshop)
- **AS-IS**: minimal — just the idea. Claude guides an interview/workshop with stakeholders.
- **TO-BE**: the main output. Claude proposes the architecture based on stakeholder input.
- **Confidence**: low — everything is GAP until validated by stakeholders.
- **Claude's role**: ask questions, propose a draft architecture, iterate with stakeholders. Fill GAPs progressively.

### Projeto legado monolítico (rewrite/decomposition)
- **AS-IS**: the monolith — one codebase, no bounded contexts, tangled dependencies. Extract the current structure honestly.
- **TO-BE**: plan the decomposition into bounded contexts. Identify seams where the monolith can be split. Prioritize contexts by independence (least coupling first).
- **Confidence**: AS-IS is CONFIRMED (code exists). TO-BE is INFERRED (decomposition is a design decision).
- **Claude's role**: identify the seams, propose bounded contexts, map the migration path (strangler fig pattern — replace context by context).
- **Example**: PROJETO_ECS (ECS legado monolítico → 8 bounded contexts M1–M8)

---

## Confidence Scale

Every element in the output (AS-IS and TO-BE) carries a confidence tag:

| Tag | Color | Meaning | Action |
|---|---|---|---|
| **CONFIRMED** | 🟢 green | Extracted directly from code or spec — verifiable, no judgment involved | Include as-is |
| **INFERRED** | 🟡 amber | Inferred from patterns, naming, or conventions — Claude's judgment, plausible but not verified | Include with `↳ inferred` annotation; flag for validation |
| **GAP** | 🔴 red | Needs human validation — no source data, conflicting sources, or ambiguous | Include as `↳ GAP: [question]`; formulate question for stakeholders |

**Rules:**
- Never present an INFERRED element as CONFIRMED.
- Never present a GAP as INFERRED.
- The traceability page shows the honest percentage of CONFIRMED traceability (not always 100%).
- The review summary (Phase 5) lists all GAPs with recommended questions.

---

## Arquitetura-alvo (TO-BE)

The target architecture for the TO-BE plan is:

**DDD + Arquitetura Hexagonal (Ports & Adapters) + TDD + Linguagem Ubíqua + UX/UI Semântica**

### DDD (Domain-Driven Design)
- **Bounded Contexts** = módulos. Cada contexto tem sua linguagem ubíqua própria.
- **Aggregate Roots** com invariantes encapsuladas. Operações só via aggregate root.
- **Value Objects** (frozen dataclasses): UnitOfMeasure, Money, DateRange, Address, Locale.
- **Domain Events** (NGEVENT): o aggregate emite eventos quando muda de estado.
- **Repositories** como ports de domínio (interfaces, não implementações).

### Hexagonal (Ports & Adapters)
- **Domain/** — entidades, aggregates, value objects, domain services, events, repository interfaces. Zero framework. Zero import de SQLAlchemy/Pydantic.
- **Application/** — use cases, ports (interfaces de inbound), DTOs.
- **Infrastructure/** — adapters: SQLAlchemy repositories, ORM models, Pydantic schemas, security.
- **API/** — inbound adapters: FastAPI routers, MCP tools.
- DB trocável via interface de repository.

### TDD (Test-Driven Development)
- Teste-primeiro (red → green → refactor).
- Testes de domínio puros (sem DB/HTTP).
- Coverage ≥85%. Mutation testing.
- Correção de defeito começa pelo teste que o reproduz.

### Linguagem Ubíqua
- PT (ou idioma do projeto), alinhada ao glossário de domínio.
- Termos consistentes entre specs, código, UI e testes.
- A taxonomia (Fase 2) é a fonte da linguagem ubíqua.

### UX/UI Semântica
- **Objetos semânticos** antes de componentes. Um objeto semântico tem: nome, papel, campos, ações, `ai_visible`.
- **ActionSpec** — catálogo de ações com `action_id`, título, `intent`, classe de risco, schema de entrada.
- **Jornadas vivas** — um documento por jornada, capturas de tela do build real por script versionado.
- **Proposta de ação** — superfície de confirmação única para ações mutadoras (humano e IA).

### Referências canônicas
- **PROJETO_ECS ADR 0004** — DDD + Hexagonal + TDD + Linguagem Ubíqua (Accepted). A descrição formal da arquitetura-alvo.
- **gestaodeprioridades `docs/governance/constitution.md`** — P1–P7: fronteira de escrita única, federação por contrato, domínio puro, TDD, observabilidade de nascença, jornada viva com prova visual, segredo nunca no cliente.
- **gestaodeprioridades spec 002** — UX design, objetos semânticos, ActionSpec, proposta-de-acao.
- **PROJETO_ECS gauntlet** — a barra de qualidade: builder + crítico cego compara o rewrite vs. legado, tela a tela.

---

## CLI

```bash
# Fase 1 — Descoberta (AS-IS)
python analyze.py <project-dir> --output as_is.json

# Fase 2 — Taxonomia
python taxonomy_builder.py as_is.json --output taxonomy.json

# Fase 3 — TO-BE Design
python to_be_planner.py as_is.json --output to_be.json

# Fase 4 — Render (merge as_is + taxonomy + to_be)
python render.py as_is.json --output docs/product-site
```

**Arguments:**
- `<project-dir>` — caminho do projeto a documentar
- `--output` — caminho do arquivo de saída (JSON ou diretório do site)

**Dependencies:** Python 3.12+, stdlib only (sem dependências externas).

---

## Design principles

- **Nomenclatura**: épico ⊃ feature ⊃ story, RF/RNF, artefato, ADR — agrupado por categoria (Produto, Engenharia, Metodologia). 15 termos, 3 categorias.
- **Rastreabilidade**: cada requisito linka forward (spec → tela → endpoint → teste) e backward (fonte legada). Percentual honesto.
- **Workflow**: 7 fases com gates verificáveis, owner, métrica, arestas de falha (fail.to + fail.action).
- **AS-IS + TO-BE**: o site mostra o que existe hoje E o que deveria existir. A diferença é o migration gap.
- **Confidence**: cada elemento taggeado CONFIRMED / INFERRED / GAP. Nunca apresentar INFERRED como CONFIRMED.
- **Design**: styles.css compartilhado, SVG icons 16px stroke=currentColor, dark mode persistente (localStorage), Inter tipografia, border-radius 8px, transitions 150ms. Régua Linear.

## References

- **PROJETO_ECS** (`D:\010_PROJETOS\130_ECS\PROJETOE_ECS`) — gauntlet 6/6, ADRs 0001–0005, 8 módulos M1–M8, 15 ciclos MAESTRO. A barra de qualidade.
- **gestaodeprioridades** (`D:\010_PROJETOS\170_GHDARU\gestaodeprioridades`) — objetos semânticos, speckit, constituição P1–P7, ADRs 0001–0019. O projeto onde a skill foi iterada 9 vezes (v1→v9, skeleton → empate).
- **Reversa** — workflow de 5 fases com 73 agentes. Referência para orquestração multi-agente de documentação.
