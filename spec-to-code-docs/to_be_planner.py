"""to_be_planner.py — TO-BE architecture planner for spec-to-code-docs v2.

Takes AS-IS JSON (from analyze.py) and produces a TO-BE plan with:
- Target architecture (DDD + Hexagonal + TDD + UXUI + Semantic Objects)
- Migration plan (Strangler Fig strategy, phases, dependencies, risks)
- Gap analysis (what's missing AS-IS → TO-BE, by module, with priority)
- Roadmap (migration phases with gates)

Heuristic (Python pure): identifies bounded contexts by grouping entities,
suggests aggregate roots, maps hexagonal layers. Generates a skeleton
that Claude refines.

Python 3.12+, stdlib only.

Usage:
    import to_be_planner
    to_be_planner.plan(as_is_data, output_path)

Or CLI:
    python to_be_planner.py input.json --output to_be.json
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────
# Heuristics for identifying domain concepts
# ──────────────────────────────────────────────────────────────────────

# Common aggregate root patterns (entity names that are typically roots)
_AGGREGATE_ROOT_HINTS = (
    "partner", "customer", "supplier", "user", "account",
    "order", "invoice", "requisition", "catalog", "product", "item",
    "auction", "bid", "quote", "shipment", "asn", "billing",
    "task", "project", "round", "journey", "session",
    "contract", "agreement", "subscription", "notification",
)

# Value object patterns (entities that are typically value objects)
_VALUE_OBJECT_HINTS = (
    "address", "money", "price", "quantity", "weight", "volume",
    "date", "period", "range", "locale", "currency", "unit",
    "coordinate", "color", "dimension", "measure",
)

# Domain event patterns
_DOMAIN_EVENT_HINTS = (
    "created", "updated", "deleted", "approved", "rejected",
    "sent", "received", "processed", "completed", "failed",
    "opened", "closed", "started", "stopped", "cancelled",
)

# Entities that are typically infrastructure (not domain)
_INFRA_HINTS = (
    "config", "setting", "log", "audit", "cache", "queue", "job",
    "migration", "seed", "token", "session_store",
)


def _is_aggregate_root(name: str) -> bool:
    """Heuristic: is this entity likely an aggregate root?"""
    n = name.lower().replace("_", "").replace("-", "")
    return any(h in n for h in _AGGREGATE_ROOT_HINTS)


# DTO suffixes — these are NOT domain entities, they are transport objects
_DTO_SUFFIXES = ("create", "update", "request", "response", "dto", "schema",
                 "input", "output", "command", "query", "form", "view")


def _is_dto(name: str) -> bool:
    """Heuristic: is this a DTO/command (not a domain entity)?"""
    n = name.lower()
    return any(n.endswith(suffix) or suffix in n for suffix in _DTO_SUFFIXES)


def _is_value_object(name: str) -> bool:
    """Heuristic: is this entity likely a value object?"""
    n = name.lower().replace("_", "").replace("-", "")
    return any(h in n for h in _VALUE_OBJECT_HINTS)


def _is_infra(name: str) -> bool:
    """Heuristic: is this entity likely infrastructure?"""
    n = name.lower().replace("_", "").replace("-", "")
    return any(h in n for h in _INFRA_HINTS)


def _classify_entity(name: str) -> str:
    """Classify an entity as aggregate_root, value_object, dto, domain_entity, or infrastructure."""
    if _is_infra(name):
        return "infrastructure"
    if _is_dto(name):
        return "dto"
    if _is_aggregate_root(name):
        return "aggregate_root"
    if _is_value_object(name):
        return "value_object"
    return "domain_entity"


def _infer_invariants(root: str) -> list[str]:
    """Infer meaningful business invariants for an aggregate root."""
    n = root.lower()
    invariants = [f"Operations on {root} only via aggregate root"]

    if "task" in n:
        invariants.append("Tasks in done status cannot be reassigned")
        invariants.append("Only todo or doing tasks can be completed")
        invariants.append("Task must have a title and an assignee to be started")
    elif "user" in n or "account" in n:
        invariants.append("User must have unique email/identifier")
        invariants.append("Inactive users cannot perform operations")
    elif "project" in n:
        invariants.append("Project must have at least one owner")
        invariants.append("Completed projects cannot have new tasks added")
    elif "order" in n or "requisition" in n:
        invariants.append("Order cannot be modified after submission for approval")
        invariants.append("Cancelled orders cannot be reactivated")
    elif "partner" in n or "customer" in n or "supplier" in n:
        invariants.append("Partner with dependents cannot be deleted")
        invariants.append("Partner type cannot be changed after transactions exist")
    elif "invoice" in n or "billing" in n:
        invariants.append("Invoice cannot be modified after issuance")
        invariants.append("Paid invoices cannot be cancelled")
    elif "auction" in n or "bid" in n:
        invariants.append("Bids cannot be placed after auction closes")
        invariants.append("Bidder cannot see other bids in blind auction")
    elif "shipment" in n or "asn" in n:
        invariants.append("Shipment cannot be modified after dispatch")
        invariants.append("Received shipments cannot be cancelled")
    else:
        invariants.append(f"{root} has consistent state")

    return invariants


# ──────────────────────────────────────────────────────────────────────
# Bounded Context identification
# ──────────────────────────────────────────────────────────────────────

def _get_nested(as_is: dict, key: str, default=None):
    """Get a key from top-level or nested as_is dict."""
    if key in as_is:
        return as_is[key]
    nested = as_is.get("as_is", {})
    if isinstance(nested, dict) and key in nested:
        return nested[key]
    return default if default is not None else []


def _infer_context_name(entity_name: str) -> str:
    """Infer a bounded context name from an entity name."""
    n = entity_name.replace("Create", "").replace("Update", "").replace("Request", "").replace("Response", "")
    # Group by theme
    n_lower = n.lower()
    if "user" in n_lower or "account" in n_lower or "auth" in n_lower:
        return "User Management"
    if "task" in n_lower:
        return "Task Management"
    if "project" in n_lower:
        return "Project Management"
    if "partner" in n_lower or "supplier" in n_lower or "customer" in n_lower:
        return "Partner Management"
    if "order" in n_lower or "requisition" in n_lower or "purchase" in n_lower:
        return "Order Management"
    if "invoice" in n_lower or "billing" in n_lower:
        return "Billing"
    if "shipment" in n_lower or "logistics" in n_lower or "asn" in n_lower:
        return "Logistics"
    if "catalog" in n_lower or "product" in n_lower or "item" in n_lower:
        return "Catalog"
    if "stock" in n_lower or "inventory" in n_lower:
        return "Inventory"
    return f"{n} Context"


def _identify_bounded_contexts(as_is: dict) -> list[dict]:
    """Identify bounded contexts from AS-IS modules/entities.

    Heuristic: group entities by module/directory or by theme.
    Never returns empty list when entities exist.
    """
    contexts = []

    # Source 1: explicit domain modules from AS-IS (top-level or nested)
    modules = _get_nested(as_is, "modules")
    # Filter: only treat as domain modules if they have entities or id
    domain_modules = [m for m in modules if isinstance(m, dict) and (m.get("entities") or m.get("id", "").startswith("M"))]
    for mod in domain_modules:
        mid = mod.get("id", mod.get("name", ""))
        mname = mod.get("name", mid)
        entities = mod.get("entities", mod.get("tables", []))
        context = _build_context(mid, mname, entities, mod)
        contexts.append(context)

    # Source 2: specs as bounded contexts (pre-implementation)
    specs = _get_nested(as_is, "specs")
    if not contexts and specs:
        for spec in specs:
            sid = spec.get("id", spec.get("spec", ""))
            sname = spec.get("name", sid)
            rfs = spec.get("rfs", [])
            entities = _extract_entities_from_rfs(rfs)
            context = _build_context(sid, sname, entities, spec)
            contexts.append(context)

    # Source 3: infer from entities (group by theme)
    if not contexts:
        entities = _get_nested(as_is, "entities")
        if not entities:
            entities = _get_nested(as_is, "tables")
        if entities:
            # Extract entity names
            ent_names = []
            for ent in entities:
                if isinstance(ent, str):
                    ent_names.append(ent)
                elif isinstance(ent, dict):
                    ent_names.append(ent.get("name", ent.get("id", str(ent))))

            # Group by inferred context name
            groups = {}
            for ename in ent_names:
                ctx_name = _infer_context_name(ename)
                if ctx_name not in groups:
                    groups[ctx_name] = []
                groups[ctx_name].append(ename)

            # Create a bounded context per group
            for ctx_name, ctx_entities in groups.items():
                cid = ctx_name.lower().replace(" ", "_")
                context = _build_context(cid, ctx_name, ctx_entities, {})
                context["confidence"] = "INFERRED"
                contexts.append(context)

    return contexts


def _build_context(cid: str, cname: str, entities: list, source: dict) -> dict:
    """Build a bounded context from entities."""
    aggregate_roots = []
    value_objects = []
    domain_entities = []
    dtos = []
    infrastructure = []

    for ent in entities:
        if isinstance(ent, str):
            name = ent
        elif isinstance(ent, dict):
            name = ent.get("name", ent.get("id", str(ent)))
        else:
            continue

        cls = _classify_entity(name)
        if cls == "aggregate_root":
            aggregate_roots.append(name)
        elif cls == "dto":
            dtos.append(name)
        elif cls == "value_object":
            value_objects.append(name)
        elif cls == "infrastructure":
            infrastructure.append(name)
        else:
            domain_entities.append(name)

    # Suggest domain events from aggregate roots only (not DTOs)
    domain_events = []
    for root in aggregate_roots:
        for event_hint in ("Created", "Updated", "Completed", "Approved", "Rejected", "Assigned"):
            domain_events.append(f"{root}{event_hint}")

    # Build hexagonal layers
    layers = {
        "domain": {
            "aggregate_roots": aggregate_roots,
            "value_objects": value_objects,
            "domain_entities": domain_entities,
            "domain_events": domain_events[:10],
            "repository_interfaces": [f"{r}Repository" for r in aggregate_roots],
            "constraints": ["Zero framework imports (no SQLAlchemy, Pydantic, etc.)", "Pure domain logic only"],
        },
        "application": {
            "use_cases": [f"Process{r}" for r in aggregate_roots[:5]],
            "ports": ["PortMCPClient", "PortRepository", "PortEventEmitter"],
            "constraints": ["Orchestrates domain + ports", "No direct infrastructure access"],
        },
        "infrastructure": {
            "adapters": ["SQLAlchemyRepository", "PydanticSchema", "FastAPIRouter", "MCPToolWrapper"],
            "orm_models": [f"{r}Model" for r in aggregate_roots],
            "dtos": dtos,
            "constraints": ["Implements domain ports", "Framework-specific code only here"],
        },
        "api": {
            "inbound": ["REST endpoints", "MCP tools", "WebSocket handlers"],
            "constraints": ["Thin controllers — delegate to use cases", "No business logic"],
        },
    }

    # Semantic objects — only real aggregate roots with meaningful invariants
    semantic_objects = []
    for root in aggregate_roots:
        semantic_objects.append({
            "name": root,
            "meaning": f"Core business concept: {root}",
            "invariants": _infer_invariants(root),
        })

    return {
        "id": cid,
        "name": cname,
        "aggregate_roots": aggregate_roots,
        "value_objects": value_objects,
        "dtos": dtos,
        "domain_events": domain_events[:10],
        "repository_ports": [f"{r}Repository" for r in aggregate_roots],
        "layers": layers,
        "semantic_objects": semantic_objects,
        "entity_count": len(entities) if entities else 0,
    }


def _extract_entities_from_rfs(rfs: list) -> list[str]:
    """Extract entity-like names from RF descriptions."""
    entities = []
    for rf in rfs:
        if isinstance(rf, dict):
            text = rf.get("d", rf.get("text", ""))
        elif isinstance(rf, str):
            text = rf
        else:
            continue
        # Look for backtick-quoted names (common in specs)
        import re
        refs = re.findall(r'`([A-Za-z_][A-Za-z0-9_]*)`', text)
        for ref in refs:
            if ref not in entities and len(ref) > 2:
                entities.append(ref)
    return entities[:20]  # limit


# ──────────────────────────────────────────────────────────────────────
# TDD Strategy
# ──────────────────────────────────────────────────────────────────────

def _build_tdd_strategy() -> dict:
    """Build TDD strategy for target architecture."""
    return {
        "approach": "Test-first (red → green → refactor)",
        "test_types": {
            "domain_tests": {
                "description": "Pure domain tests — no DB, no HTTP, no framework",
                "scope": "aggregate roots, value objects, domain events, invariants",
                "constraint": "Zero imports from infrastructure",
            },
            "use_case_tests": {
                "description": "Application layer tests with mocked ports",
                "scope": "use cases, port interactions",
            },
            "integration_tests": {
                "description": "Adapter tests with real DB (testcontainers) / real HTTP",
                "scope": "repository implementations, API endpoints",
            },
            "e2e_tests": {
                "description": "End-to-end flux tests (gauntlet bar)",
                "scope": "full user journeys",
            },
        },
        "coverage_target": "≥85%",
        "mutation_testing": True,
        "gauntlet": "Builder + crítico cego compara TO-BE vs. AS-IS, fluxo a fluxo",
    }


# ──────────────────────────────────────────────────────────────────────
# UXUI Strategy
# ──────────────────────────────────────────────────────────────────────

def _build_uxui_strategy(as_is: dict) -> dict:
    """Build UXUI strategy from AS-IS data."""
    # Extract telas/screens from AS-IS
    telas = []
    for mod in _get_nested(as_is, "modules"):
        for tela in mod.get("telas", mod.get("screens", [])):
            telas.append(tela if isinstance(tela, str) else tela.get("name", str(tela)))

    journeys = _get_nested(as_is, "journeys")

    return {
        "design_system": {
            "tokens": ["color", "typography", "spacing", "radius", "shadow"],
            "components": ["Button", "Input", "Table", "Modal", "Card", "Nav", "Form"],
            "dark_mode": True,
            "i18n": ["pt", "en", "es"],
            "accessibility": "WCAG 2.1 AA",
        },
        "semantic_objects_ui": {
            "description": "Telas e componentes com significado de negócio, não apenas técnico",
            "approach": "Cada tela mapeia a um ou mais objetos semânticos de domínio",
        },
        "telas": telas[:20],
        "jornadas": [{"id": j.get("id", ""), "name": j.get("name", "")} for j in journeys] if isinstance(journeys, list) else [],
    }


# ──────────────────────────────────────────────────────────────────────
# Migration Plan
# ──────────────────────────────────────────────────────────────────────

def _build_migration_plan(contexts: list[dict], as_is: dict) -> dict:
    """Build migration plan using Strangler Fig strategy."""
    # Determine strategy
    modules = _get_nested(as_is, "modules")
    endpoints = _get_nested(as_is, "endpoints")
    specs = _get_nested(as_is, "specs")
    has_code = bool(modules or endpoints)
    has_specs = bool(specs)
    if has_code and has_specs:
        strategy = "Strangler Fig"
        rationale = "Sistema existente com specs — migrar incrementalmente, substituindo fluxos um a um"
    elif has_code and not has_specs:
        strategy = "Incremental refactor from flat to DDD"
        rationale = "Código existente sem specs — refatorar de flat/monolítico para DDD+Hexagonal incrementalmente"
    else:
        strategy = "Greenfield spec-driven"
        rationale = "Sem código de produção — construir do zero com TDD, spec como fonte de verdade"

    # Build phases
    phases = []
    for i, ctx in enumerate(contexts):
        phase = {
            "n": i + 1,
            "bounded_context": ctx["id"],
            "name": ctx["name"],
            "goal": f"Migrar {ctx['name']} para DDD + Hexagonal",
            "activities": [
                f"Definir aggregate roots: {', '.join(ctx['aggregate_roots'][:5])}",
                f"Implementar domain/ puro (sem framework)",
                f"Implementar repositories (ports + adapters)",
                f"Implementar use cases (application/)",
                f"Implementar API endpoints + MCP tools (api/)",
                f"Testes de domínio + integração + E2E",
            ],
            "gates": [
                "Domain layer sem imports de framework",
                "Coverage ≥85%",
                "Gauntlet: crítico cego aprova",
            ],
            "dependencies": [contexts[j]["id"] for j in range(i) if contexts[j]["id"] != ctx["id"] and j < i],
        }
        phases.append(phase)

    # Risks
    risks = [
        {"risk": "Resistência à mudança de arquitetura", "mitigation": "Treinamento DDD + pair programming", "severity": "medium"},
        {"risk": "Complexidade de migração de dados", "mitigation": "Migrations idempotentes + seeds versionados", "severity": "high"},
        {"risk": "Regression em fluxos existentes", "mitigation": "E2E tests como gauntlet + parallel run", "severity": "high"},
        {"risk": "Over-engineering de bounded contexts", "mitigation": "YAGNI — só modelar o que o spec exige", "severity": "low"},
    ]

    return {
        "strategy": strategy,
        "rationale": rationale,
        "phases": phases,
        "risks": risks,
        "rollback_plan": "Manter AS-IS rodando em paralelo durante migração. Rollback por fluxo, não global.",
    }


# ──────────────────────────────────────────────────────────────────────
# Gap Analysis
# ──────────────────────────────────────────────────────────────────────

def _build_gap_analysis(contexts: list[dict], as_is: dict) -> dict:
    """Build gap analysis: what's missing AS-IS → TO-BE."""
    gaps = []

    has_code = bool(_get_nested(as_is, "modules") or _get_nested(as_is, "endpoints"))

    for ctx in contexts:
        ctx_gaps = []

        # Check if domain layer exists
        if not has_code:
            ctx_gaps.append({
                "gap": "Domain layer não existe",
                "target": f"domain/ com aggregate roots: {', '.join(ctx['aggregate_roots'][:3])}",
                "priority": "critical",
                "effort": "medium",
            })

        # Check if tests exist
        testes = 0
        for mod in _get_nested(as_is, "modules"):
            testes += mod.get("testes", 0)
        if testes == 0:
            ctx_gaps.append({
                "gap": "Sem testes de domínio",
                "target": "TDD: testes de domínio puros + integração + E2E",
                "priority": "critical",
                "effort": "high",
            })

        # Check if MCP tools exist
        tools = sum(mod.get("tools", 0) for mod in _get_nested(as_is, "modules"))
        if tools == 0:
            ctx_gaps.append({
                "gap": "Sem MCP tools",
                "target": "MCP tools como adapter inbound (api/mcp.py)",
                "priority": "medium",
                "effort": "medium",
            })

        # Check if hexagonal structure exists
        ctx_gaps.append({
            "gap": "Estrutura hexagonal (domain/application/infrastructure/api)",
            "target": "Portas e adapters separados, domínio sem framework",
            "priority": "high",
            "effort": "medium",
        })

        # Check if semantic objects are identified
        if not ctx.get("semantic_objects"):
            ctx_gaps.append({
                "gap": "Objetos semânticos não identificados",
                "target": f"Identificar objetos de domínio com significado de negócio",
                "priority": "medium",
                "effort": "low",
            })

        gaps.append({
            "bounded_context": ctx["id"],
            "name": ctx["name"],
            "gaps": ctx_gaps,
            "gap_count": len(ctx_gaps),
        })

    # Summary
    total_gaps = sum(g["gap_count"] for g in gaps)
    critical = sum(1 for g in gaps for gap in g["gaps"] if gap["priority"] == "critical")
    high = sum(1 for g in gaps for gap in g["gaps"] if gap["priority"] == "high")

    return {
        "gaps_by_context": gaps,
        "summary": {
            "total_gaps": total_gaps,
            "critical": critical,
            "high": high,
            "contexts_analyzed": len(contexts),
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Roadmap TO-BE
# ──────────────────────────────────────────────────────────────────────

def _build_roadmap(contexts: list[dict], migration_plan: dict) -> dict:
    """Build TO-BE roadmap with phases and gates."""
    phases = []
    for i, ctx in enumerate(contexts):
        phases.append({
            "n": i + 1,
            "title": ctx["name"],
            "bounded_context": ctx["id"],
            "gates": ["F0✓", "F1✓", "F2○", "F3○", "F4○", "F5○"],
            "status": "planned",
            "deliverables": [
                f"spec.md para {ctx['name']}",
                f"domain/ com {len(ctx['aggregate_roots'])} aggregate roots",
                f"application/ use cases",
                f"infrastructure/ adapters",
                f"api/ endpoints + MCP tools",
                f"tests (domain + integration + E2E)",
            ],
        })

    return {
        "phases": phases,
        "gates_definition": {
            "F0": "Inventário & Extração",
            "F1": "Spec aprovada",
            "F2": "Plan & Tasks",
            "F3": "Build (TDD) — coverage ≥85%",
            "F4": "Gauntlet — crítico cego aprova",
            "F5": "Deploy — health 200 + E2E",
        },
        "strategy": migration_plan["strategy"],
    }


# ──────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────

def plan(as_is: dict) -> dict:
    """Generate TO-BE plan from AS-IS data.

    Args:
        as_is: JSON dict from analyze.py with modules, entities, specs, etc.

    Returns:
        TO-BE JSON dict with target_architecture, migration_plan, gap_analysis, roadmap.
    """
    # 1. Identify bounded contexts
    contexts = _identify_bounded_contexts(as_is)

    # 2. Build target architecture
    target_architecture = {
        "paradigm": "DDD + Hexagonal + TDD + Linguagem Ubíqua",
        "bounded_contexts": contexts,
        "tdd_strategy": _build_tdd_strategy(),
        "uxui": _build_uxui_strategy(as_is),
        "semantic_objects": [
            {"context": ctx["id"], "objects": ctx["semantic_objects"]}
            for ctx in contexts
        ],
        "principles": [
            "Domain layer pure — zero framework imports",
            "Aggregate roots encapsulate invariants",
            "Operations only via aggregate root",
            "Ports (interfaces) in domain, adapters (implementations) in infrastructure",
            "TDD: test-first (red → green → refactor)",
            "Linguagem ubíqua: PT, alinhada ao glossário de negócio",
            "YAGNI: não inventar além do spec",
        ],
    }

    # 3. Build migration plan
    migration_plan = _build_migration_plan(contexts, as_is)

    # 4. Build gap analysis
    gap_analysis = _build_gap_analysis(contexts, as_is)

    # 5. Build roadmap
    roadmap = _build_roadmap(contexts, migration_plan)

    return {
        "target_architecture": target_architecture,
        "migration_plan": migration_plan,
        "gap_analysis": gap_analysis,
        "roadmap": roadmap,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="TO-BE architecture planner")
    parser.add_argument("input", help="Path to AS-IS JSON file (from analyze.py)")
    parser.add_argument("--output", "-o", default="to_be.json", help="Output TO-BE JSON path")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        as_is = json.load(f)

    to_be = plan(as_is)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(to_be, f, ensure_ascii=False, indent=2)

    print(f"TO-BE plan written to {args.output}")


if __name__ == "__main__":
    main()
