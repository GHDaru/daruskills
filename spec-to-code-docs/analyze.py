"""analyze.py — Reverse-engineering engine for spec-to-code-docs v2.

Entry point of the v2 pipeline. Replaces generate.py. Works on ANY project,
including code-only (no specs). Scans code, extracts architecture, assigns
confidence (CONFIRMED/INFERRED/GAP), and outputs JSON for render.py.

Python 3.12+, stdlib only.

Usage:
    python analyze.py <project_dir> [--output file.json]
    python analyze.py D:/.../test-project
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _first_line_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _strip_emphasis(s: str) -> str:
    return re.sub(r"`?\*{1,2}(.*?)\*{1,2}`?", r"\1", s).strip()


# ──────────────────────────────────────────────────────────────────────
# Stack detection
# ──────────────────────────────────────────────────────────────────────

def detect_stack(project: Path) -> dict:
    """Detect language/stack from project files."""
    stack = {"language": "", "framework": "", "backend": "", "frontend": "", "banco": "", "confidence": "confirmed"}

    if (project / "pyproject.toml").exists() or (project / "setup.py").exists():
        stack["language"] = "Python"
        text = _read(project / "pyproject.toml") or _read(project / "setup.py")
        if "fastapi" in text.lower():
            stack["framework"] = "FastAPI"
            stack["backend"] = "FastAPI (Python)"
        elif "django" in text.lower():
            stack["framework"] = "Django"
            stack["backend"] = "Django (Python)"
        elif "flask" in text.lower():
            stack["framework"] = "Flask"
            stack["backend"] = "Flask (Python)"
        else:
            stack["backend"] = "Python"

    if (project / "package.json").exists():
        text = _read(project / "package.json")
        if not stack["language"]:
            stack["language"] = "JavaScript/TypeScript"
        if "react" in text.lower():
            stack["frontend"] = "React"
        elif "vue" in text.lower():
            stack["frontend"] = "Vue"
        elif "express" in text.lower():
            stack["backend"] = stack["backend"] or "Express (Node)"

    if (project / "pom.xml").exists():
        stack["language"] = "Java"
        text = _read(project / "pom.xml")
        if "spring" in text.lower():
            stack["framework"] = "Spring Boot"
            stack["backend"] = "Spring Boot (Java)"

    if (project / "go.mod").exists():
        stack["language"] = "Go"
        stack["backend"] = "Go"

    if (project / "composer.json").exists():
        stack["language"] = "PHP"
        text = _read(project / "composer.json")
        if "laravel" in text.lower():
            stack["framework"] = "Laravel"
            stack["backend"] = "Laravel (PHP)"

    return stack


# ──────────────────────────────────────────────────────────────────────
# Python code scanner
# ──────────────────────────────────────────────────────────────────────

def _scan_python_file(path: Path, project: Path) -> dict:
    """Scan a single Python file for classes, functions, endpoints, imports."""
    text = _read(path)
    rel_path = str(path.relative_to(project))

    result = {
        "path": rel_path,
        "classes": [],
        "functions": [],
        "endpoints": [],
        "imports": [],
        "dataclasses": [],
        "decorators": [],
    }

    # Imports
    for m in re.finditer(r"^(?:from\s+(\S+)\s+import|import\s+(\S+))", text, re.M):
        imp = m.group(1) or m.group(2)
        if imp and not imp.startswith("."):
            result["imports"].append(imp)

    # Classes
    for m in re.finditer(r"^class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:", text, re.M):
        cname = m.group(1)
        bases = (m.group(2) or "").strip()
        is_dataclass = "@dataclass" in text[max(0, m.start() - 200):m.start()]
        entry = {"name": cname, "bases": bases, "is_dataclass": is_dataclass, "confidence": "confirmed"}
        result["classes"].append(entry)
        if is_dataclass:
            result["dataclasses"].append(cname)

    # Functions (def, not inside class)
    for m in re.finditer(r"^(?:\s+)def\s+(\w+)\s*\(", text, re.M):
        fname = m.group(1)
        if not fname.startswith("_"):
            result["functions"].append(fname)

    # Endpoints: @app.get("/path"), @router.post("/path"), etc.
    for m in re.finditer(r"@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", text):
        method = m.group(1).upper()
        path_route = m.group(2)
        result["endpoints"].append({"method": method, "path": path_route, "confidence": "confirmed"})

    # Decorators
    for m in re.finditer(r"@(\w+)", text):
        dec = m.group(1)
        if dec not in ("staticmethod", "classmethod", "property", "dataclass"):
            result["decorators"].append(dec)

    return result


def scan_python_code(project: Path) -> dict:
    """Scan all Python files in the project."""
    py_files = sorted(project.rglob("*.py"))
    # Exclude common non-source dirs
    py_files = [f for f in py_files if not any(p in str(f) for p in ("__pycache__", ".venv", "venv", "node_modules", ".git", "/tests/"))]

    modules = []
    entities = []
    endpoints = []
    all_functions = []
    all_imports = []

    for f in py_files:
        scan = _scan_python_file(f, project)
        modules.append({"name": scan["path"], "confidence": "confirmed"})

        # Dataclasses and classes with bases = entities
        for cls in scan["classes"]:
            if cls["is_dataclass"] or any(b in cls["bases"] for b in ("BaseModel", "Model")):
                entities.append({"name": cls["name"], "module": scan["path"], "confidence": "confirmed"})

        endpoints.extend(scan["endpoints"])
        all_functions.extend(scan["functions"])
        all_imports.extend(scan["imports"])

    return {
        "modules": modules,
        "entities": entities,
        "endpoints": endpoints,
        "functions": all_functions,
        "imports": list(set(all_imports)),
    }


# ──────────────────────────────────────────────────────────────────────
# JS/TS code scanner
# ──────────────────────────────────────────────────────────────────────

def scan_js_code(project: Path) -> dict:
    """Scan JS/TS files for classes, functions, endpoints."""
    js_files = sorted(project.rglob("*.js")) + sorted(project.rglob("*.ts"))
    js_files = [f for f in js_files if "node_modules" not in str(f) and ".git" not in str(f)]

    modules = []
    entities = []
    endpoints = []
    all_functions = []

    for f in js_files:
        text = _read(f)
        rel_path = str(f.relative_to(project))
        modules.append({"name": rel_path, "confidence": "confirmed"})

        # Classes
        for m in re.finditer(r"\bclass\s+(\w+)", text):
            entities.append({"name": m.group(1), "module": rel_path, "confidence": "confirmed"})

        # Functions
        for m in re.finditer(r"(?:export\s+)?function\s+(\w+)", text):
            all_functions.append(m.group(1))

        # Endpoints: app.get("/path"), router.post("/path")
        for m in re.finditer(r"(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*[\"'`]([^\"'`]+)[\"'`]", text):
            endpoints.append({"method": m.group(1).upper(), "path": m.group(2), "confidence": "confirmed"})

    return {"modules": modules, "entities": entities, "endpoints": endpoints, "functions": all_functions, "imports": []}


# ──────────────────────────────────────────────────────────────────────
# Architecture detection
# ──────────────────────────────────────────────────────────────────────

def detect_architecture(project: Path, code_scan: dict) -> dict:
    """Detect architecture style from directory structure and imports."""
    # Check for DDD/Hexagonal patterns
    has_domain = any("domain" in str(p) for p in project.rglob("*"))
    has_application = any("application" in str(p) for p in project.rglob("*"))
    has_infrastructure = any("infrastructure" in str(p) for p in project.rglob("*"))
    has_use_cases = any("use_case" in str(p).lower() for p in project.rglob("*"))
    has_repositories = any("repository" in str(p).lower() for p in project.rglob("*"))

    # Check for MVC
    has_controllers = any("controller" in str(p).lower() for p in project.rglob("*"))
    has_views = any("view" in str(p).lower() for p in project.rglob("*"))

    # Check for modules dirs
    has_modules_dir = any(p.is_dir() and p.name.startswith("m") and "_" in p.name for p in project.rglob("*"))

    if has_domain and has_application and has_infrastructure:
        style = "DDD + Hexagonal"
        confidence = "confirmed"
        evidence = "domain/ + application/ + infrastructure/ dirs found"
    elif has_domain and has_use_cases:
        style = "DDD (partial)"
        confidence = "confirmed"
        evidence = "domain/ + use_cases found"
    elif has_modules_dir:
        style = "Modular monolith"
        confidence = "inferred"
        evidence = "module dirs (mN_*) found"
    elif has_controllers and has_views:
        style = "MVC"
        confidence = "inferred"
        evidence = "controller + view dirs found"
    else:
        # Check if flat: all code in one dir or src/
        src_dirs = [p for p in project.iterdir() if p.is_dir() and p.name in ("src", "app", "lib")]
        if src_dirs or len(code_scan["modules"]) <= 10:
            style = "Flat / monolithic"
            confidence = "inferred"
            evidence = f"no architectural dirs found, {len(code_scan['modules'])} files in flat structure"
        else:
            style = "Unknown"
            confidence = "gap"
            evidence = "could not determine architecture"

    return {"style": style, "confidence": confidence, "evidence": evidence}


# ──────────────────────────────────────────────────────────────────────
# Business rule extraction
# ──────────────────────────────────────────────────────────────────────

def extract_business_rules(code_scan: dict) -> list[dict]:
    """Extract implicit business rules from function names and patterns."""
    rules = []
    # Domain verbs that indicate business rules
    domain_verbs = {
        "create": "Criação",
        "assign": "Atribuição",
        "complete": "Conclusão",
        "validate": "Validação",
        "calculate": "Cálculo",
        "prioritize": "Priorização",
        "cancel": "Cancelamento",
        "approve": "Aprovação",
        "reject": "Rejeição",
        "update": "Atualização",
        "delete": "Exclusão",
        "list": "Listagem",
        "get": "Consulta",
    }

    seen = set()
    for func in code_scan.get("functions", []):
        func_lower = func.lower()
        for verb, label in domain_verbs.items():
            if verb in func_lower and func not in seen:
                seen.add(func)
                rules.append({
                    "name": func,
                    "type": label,
                    "confidence": "inferred",
                    "description": f"Função {func} — regra de {label.lower()} implícita no nome",
                })
                break

    return rules


# ──────────────────────────────────────────────────────────────────────
# Specs and ADRs (reuse from generate.py patterns)
# ──────────────────────────────────────────────────────────────────────

def _extract_status(text: str) -> str:
    m = re.search(r"Status\*?\*?:\s*\*{0,2}(\w+)\*{0,2}", text, re.I)
    return m.group(1).strip() if m else ""


def scan_specs(project: Path) -> list[dict]:
    """Scan specs/*/spec.md if they exist."""
    specs = []
    for spec_md in sorted(project.glob("specs/*/spec.md")):
        text = _read(spec_md)
        spec_id = spec_md.parent.name
        title = _first_line_heading(text) or spec_id
        status = _extract_status(text)
        # Extract RFs
        rfs = []
        for m in re.finditer(r"(?:^|\n)[-*\s]*\*{0,2}(RF[-]?\d+)\*{0,2}\s*[:：—–-]\s*(.+?)(?=\n[-*\s]*\*{0,2}R[FN]|\n##|\n###|\Z)", text, re.DOTALL):
            rid = m.group(1).replace("RF-", "RF")
            desc = re.sub(r"\s+", " ", m.group(2).strip())
            desc = _strip_emphasis(desc)
            rfs.append({"id": rid, "d": desc, "s": "", "confidence": "confirmed"})
        specs.append({
            "id": spec_id, "name": title, "status": status,
            "rfs": rfs, "rf": len(rfs),
            "specPath": str(spec_md.relative_to(project)),
            "confidence": "confirmed",
        })
    return specs


def scan_adrs(project: Path) -> list[dict]:
    """Scan docs/adr/*.md if they exist."""
    adrs = []
    for f in sorted(project.glob("docs/adr/*.md")):
        if f.name == "README.md":
            continue
        text = _read(f)
        title = _first_line_heading(text)
        m = re.search(r"(\d+)", f.name)
        n = m.group(1) if m else ""
        status = ""
        m_s = re.search(r"Status\*?\*?:\s*\*{0,2}(\w+)\*{0,2}", text, re.I)
        if m_s:
            status = m_s.group(1).strip()
        clean_title = re.sub(r"^ADR\s*\d+\s*[—–\-]\s*", "", title).strip() or title
        adrs.append({"n": n, "title": clean_title, "status": status, "confidence": "confirmed"})
    return adrs


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def analyze(project_dir: str | Path) -> dict:
    """Analyze a project directory and produce JSON for render.py."""
    project = Path(project_dir).resolve()

    # 1. Detect stack
    stack = detect_stack(project)

    # 2. Scan code
    if stack["language"] == "Python":
        code_scan = scan_python_code(project)
    elif stack["language"] in ("JavaScript/TypeScript", "Java", "Go", "PHP"):
        code_scan = scan_js_code(project)
    else:
        # Try Python first, then JS
        code_scan = scan_python_code(project)
        if not code_scan["modules"]:
            code_scan = scan_js_code(project)

    # 3. Detect architecture
    architecture = detect_architecture(project, code_scan)

    # 4. Extract business rules
    rules = extract_business_rules(code_scan)

    # 5. Scan specs/ADRs
    specs = scan_specs(project)
    adrs = scan_adrs(project)

    # 6. Build AS-IS
    as_is = {
        "modules": code_scan["modules"],
        "entities": code_scan["entities"],
        "endpoints": code_scan["endpoints"],
        "rules": rules,
        "architecture": architecture,
        "functions": code_scan.get("functions", []),
        "imports": code_scan.get("imports", []),
        "confidence": architecture["confidence"],
    }

    # 7. Overview
    claude_text = _read(project / "CLAUDE.md") or _read(project / "README.md")
    project_name = _first_line_heading(claude_text) or project.name
    lede = ""
    for line in claude_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") and stripped != ">":
            lede += stripped.lstrip("> ").strip() + " "
        elif lede and not stripped.startswith(">"):
            break
    lede = lede.strip() or f"{stack.get('language', 'Unknown')} project — {architecture['style']}"

    overview = {
        "eyebrow": "Visão geral",
        "title": project_name,
        "lede": lede,
        "cards": [{"title": "Stack", "content": f"{stack.get('language','')} · {stack.get('framework','')}"}],
    }

    # 8. Metrics
    metrics = [
        ["Linguagem", stack.get("language", "Unknown")],
        ["Framework", stack.get("framework", "—")],
        ["Arquitetura", architecture["style"]],
        ["Módulos/arquivos", str(len(code_scan["modules"]))],
        ["Entidades", str(len(code_scan["entities"]))],
        ["Endpoints", str(len(code_scan["endpoints"]))],
        ["Regras de negócio", str(len(rules))],
        ["Specs", str(len(specs))],
        ["ADRs", str(len(adrs))],
    ]

    # 9. Project metadata
    project_meta = {
        "name": project_name,
        "subtitle": f"{architecture['style']} · {stack.get('language', '')}",
        "lang": "pt-BR",
        "gauntlet": "—",
    }

    return {
        "project": project_meta,
        "overview": overview,
        "stack": stack,
        "as_is": as_is,
        "specs": specs,
        "adrs": adrs,
        "metrics": metrics,
        "modules": [],
        "skills": [],
        "scripts": [],
        "journeys": [],
        "prototype": None,
        "traceability": {"modules": []},
        "roadmap": {},
        "taxonomy": {"categories": [], "terms": []},
        "workflow": {"phases": []},
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze a project directory for spec-to-code-docs v2.")
    parser.add_argument("project", help="Path to the project directory")
    parser.add_argument("--output", "-o", help="Output JSON file path (default: stdout)")
    args = parser.parse_args()

    data = analyze(args.project)
    output = json.dumps(data, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"JSON written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
