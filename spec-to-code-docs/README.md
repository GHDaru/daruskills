# spec-to-code-docs

A Claude Code skill that generates a **navigable documentation site** tracing from business source through specs and deliverables to code.

## What it produces

A static HTML site in `docs/product-site/` with:
- **index.html** — overview, taxonomy (15 product terms), workflow (7 phases with gates + failure edges), ADRs, metrics, artifacts
- **modules.html** — specs/modules as epics with features, acceptance criteria, dependencies
- **traceability.html** — requirements (RF/RNF) with forward chain (spec → screen → endpoint → test) and backward chain (legacy source)
- **roadmap.html** — cycles with temporal axis (Now/Next/Later), gates, dependencies
- **styles.css** — shared Linear-grade design (Inter, SVG icons, dark mode, border-radius 8px)

## Install

### Any project (Mac/Linux/Git Bash)
```bash
./install.sh /path/to/your/project
```

### Windows (PowerShell)
```powershell
.\install.ps1 C:\path\to\your\project
```

This copies the skill to `<project>/.claude/skills/spec-to-code-docs/` so Claude Code discovers it automatically.

## Use

### Via Claude (recommended)
Just ask Claude in the target project:
> "Document this project with spec-to-code-docs"

Claude will discover the skill and run it.

### Via CLI
```bash
python .claude/skills/spec-to-code-docs/generate.py . --output docs/product-site/data.json
python .claude/skills/spec-to-code-docs/render.py docs/product-site/data.json --output docs/product-site
```

Then open `docs/product-site/index.html` in a browser.

## Requirements

- Python 3.12+ (stdlib only — no pip install needed)
- The target project should have specs (specs/*/spec.md), ADRs (docs/adr/), or similar. Works on projects with or without production code.

## What the skill discovers

| Source | Extracted |
|--------|-----------|
| specs/*/spec.md | Title, status, artifacts, RF/RNF (EARS syntax) |
| docs/adr/*.md | Number, title, status, context, decision |
| skills/*/SKILL.md | Name, description |
| scripts/* | Name, type (Python/Bash/Node) |
| docs/jornadas/* | Journey name, step count |
| CLAUDE.md / README.md | Project overview, stack |
| backend/app/modules/ or src/ | Modules, endpoints, tests |
| docs/roadmap.md | Cycles, gates, dependencies |

## Quality bar

Built and validated via a gauntlet loop (9 iterations) against the PROJETO_ECS product site (gauntlet 6/6 vs Atlassian, GitLab, Linear). Result: **empate** — the skill produces sites of the same quality as the hand-built reference.

## Files

```
spec-to-code-docs/
├── SKILL.md           ← skill instructions (with frontmatter for Claude discovery)
├── generate.py        ← discovery + data extraction (Python 3.12+, stdlib only)
├── render.py          ← HTML renderer (produces 4 pages + styles.css)
├── install.sh         ← installer (Mac/Linux/Git Bash)
├── install.ps1        ← installer (Windows PowerShell)
├── README.md          ← this file
├── target-inventory.md ← example inventory (gestaodeprioridades)
└── templates/
    ├── styles.css     ← shared Linear-grade design
    └── progress.html  ← progress page template
```
