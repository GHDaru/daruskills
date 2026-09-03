"""taxonomy_builder.py — Builds project-specific taxonomy for spec-to-code-docs v2.

v1 uses 15 fixed glossary terms. v2 builds a PROJECT-SPECIFIC taxonomy by:
  1. Keeping the 15 UNIVERSAL product-management terms (fixed, 3 categories).
  2. Extracting DOMAIN terms from the project (code, specs, modules, acronyms).
  3. MAPPING domain terms to universal terms (e.g. "Partner" → "Aggregate Root").

Input:  JSON dict from generate.py (or analyze.py) + optional project_dir for code scanning.
Output: JSON with {universal_terms, domain_terms, mappings, categories}.

Python 3.12+, stdlib only.

Usage:
    from taxonomy_builder import build_taxonomy
    taxonomy = build_taxonomy(data, project_dir="path/to/project")

    # Or CLI:
    # python taxonomy_builder.py input.json --project-dir ./myproject --output taxonomy.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any


# ──────────────────────────────────────────────────────────────────────
# 1. UNIVERSAL TERMS — 15 fixed product-management terms (same as v1)
# ──────────────────────────────────────────────────────────────────────

UNIVERSAL_CATEGORIES = [
    {"key": "produto",      "label": "Produto",      "icon": "📦", "hint": "Épico ⊃ Feature ⊃ Story — a hierarquia de valor de negócio"},
    {"key": "engenharia",   "label": "Engenharia",   "icon": "⚙️", "hint": "Módulo, Spec, ADR, DDD/Hexagonal — a estrutura técnica"},
    {"key": "metodologia",  "label": "Metodologia",  "icon": "📋", "hint": "Gauntlet, Jornada — como trabalhamos"},
]

UNIVERSAL_TERMS = [
    {"term": "Épico (Epic)", "id": "epic", "cat": "produto", "def": "Grande corpo de trabalho que agrega valor de negócio, decomposto em features entregáveis.", "map": "Cada módulo ou spec principal é um épico.", "analogy": "Como um capítulo de livro."},
    {"term": "Feature", "id": "feature", "cat": "produto", "def": "Funcionalidade entregável e julgável isoladamente, decomposta em stories.", "map": "Cada tela, endpoint ou grupo de tools MCP é uma feature.", "analogy": "Como uma seção do capítulo."},
    {"term": "Story", "id": "story", "cat": "produto", "def": "Unidade de trabalho entregável num ciclo, decomposta de uma feature.", "map": "Cada tarefa em tasks.md com critérios de aceitação.", "analogy": "Como um parágrafo — entregável isolado."},
    {"term": "Requisito Funcional (RF)", "id": "rf", "cat": "produto", "def": "O que o sistema faz — comportamento observável, regra de negócio.", "map": "Seção §3 de cada spec. Sintaxe EARS: WHEN/IF/THE SYSTEM SHALL.", "analogy": "O \"o que\" — a funcionalidade."},
    {"term": "Requisito Não-Funcional (RNF)", "id": "rnf", "cat": "produto", "def": "Como o sistema se comporta — performance, segurança, i18n, acessibilidade.", "map": "Seção §4 de cada spec. Superior ao legado é o gauntlet.", "analogy": "O \"como\" — as qualidades."},
    {"term": "Critério de Aceitação", "id": "aceitacao", "cat": "produto", "def": "Condições verificáveis que devem ser verdade para considerar a feature/story pronta.", "map": "O gauntlet é o DoD — o crítico cego verifica.", "analogy": "A definição de pronto."},
    {"term": "Roadmap", "id": "roadmap", "cat": "produto", "def": "Sequência temporal dos ciclos de trabalho.", "map": "Progressão dos ciclos e os gates do gauntlet.", "analogy": "O índice do livro."},
    {"term": "Módulo (Bounded Context)", "id": "module", "cat": "engenharia", "def": "Fronteira de domínio com linguagem ubíqua própria. Raiz do DDD/Hexagonal.", "map": "backend/app/modules/mN_* + frontend/src/features/mN-*.", "analogy": "O território do domínio."},
    {"term": "Spec", "id": "spec", "cat": "engenharia", "def": "Especificação — fonte de verdade de um módulo. Gerada antes da construção.", "map": "specs/NNN-*/spec.md — seções padronizadas.", "analogy": "A partitura da orquestra."},
    {"term": "Artefato", "id": "artifact", "cat": "engenharia", "def": "Qualquer entregável produzido: spec.md, plan.md, tasks.md, qa-report.md, ADR, tela, endpoint.", "map": "Um spec gera 4+ artefatos: spec · plan · tasks · qa-report.", "analogy": "A prova de que tocamos."},
    {"term": "ADR", "id": "adr", "cat": "engenharia", "def": "Architecture Decision Record — decisão imutável e datada, com contexto e consequências.", "map": "docs/adr/NNNN.md — Nunca reescrita.", "analogy": "A ata da decisão — imutável."},
    {"term": "Aggregate Root", "id": "aggregate", "cat": "engenharia", "def": "DDD — entidade raiz que encapsula invariantes; operações só via ela.", "map": "Partner, CatalogueItem, ASN, Auction, Billing.", "analogy": "A porta de entrada do domínio."},
    {"term": "Port / Adapter", "id": "port", "cat": "engenharia", "def": "Hexagonal — port é a interface de domínio (sem framework); adapter é a implementação.", "map": "domain/repositories/ (port) ↔ infrastructure/ (adapter).", "analogy": "O contrato e o prestador."},
    {"term": "Gauntlet", "id": "gauntlet", "cat": "metodologia", "def": "Barra de qualidade: builder + crítico cego compara o rewrite vs. o legado.", "map": "Crítico compara cego tela-a-tela vs. documentação legada.", "analogy": "O júri cego."},
    {"term": "Jornada", "id": "jornada", "cat": "metodologia", "def": "Demo guiada que percorre um fluxo de negócio ponta-a-ponta, passo a passo.", "map": "Jornadas com target_selector e spotlight.", "analogy": "A tour guiada pelo museu."},
]


# ──────────────────────────────────────────────────────────────────────
# 2. DOMAIN TERM EXTRACTION
# ──────────────────────────────────────────────────────────────────────

@dataclass
class DomainTerm:
    """A domain-specific term extracted from the project."""
    term: str
    definition: str = ""
    category: str = "Domain"
    source: str = ""          # file/class where found
    confidence: str = "INFERRED"  # CONFIRMED | INFERRED | GAP
    kind: str = ""            # entity | value_object | repository | module | acronym | glossary


@dataclass
class Mapping:
    """Maps a domain term to a universal term."""
    domain_term: str
    universal_term: str       # id of universal term
    confidence: str = "INFERRED"
    reason: str = ""


# ── Stop words for filtering noise from domain term extraction ──
_STOP_WORDS = frozenset({
    "the", "system", "shall", "when", "if", "then", "else", "end", "for",
    "and", "or", "not", "all", "new", "self", "true", "false", "none", "null",
    "class", "def", "import", "from", "return", "raise", "with", "async",
    "await", "yield", "pass", "break", "continue", "while", "lambda",
    "init", "str", "int", "float", "bool", "dict", "list", "set", "tuple",
    "any", "type", "super", "cls", "args", "kwargs", "property", "staticmethod",
    "classmethod", "abstractmethod", "dataclass", "field", "asdict",
    # Portuguese common
    "sistema", "deve", "devem", "quando", "entao", "então", "onde", "como",
    "para", "por", "com", "sem", "sobre", "apos", "após", "antes", "durante",
    "entre", "até", "ate", "desde", "contra", "sob", "cada", "todo", "toda",
    "todos", "todas", "outro", "outra", "mesmo", "mesma", "este", "esta",
    "esse", "essa", "aquele", "aquela", "isso", "disso", "disto", "qual",
    "quais", "seja", "ser", "estar", "ter", "ir", "fazer", "dizer", "ver",
    "dar", "obter", "poder", "querer", "dever", "haver",
})


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_classes_from_python(text: str) -> list[tuple[str, str]]:
    """Extract (class_name, base_class) from Python source.
    Returns list of (name, bases) tuples."""
    classes = []
    for m in re.finditer(r"^class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:", text, re.M):
        name = m.group(1)
        bases = (m.group(2) or "").strip()
        classes.append((name, bases))
    return classes


def _extract_from_code(project_dir: Path) -> list[DomainTerm]:
    """Extract domain terms from Python code (DDD/Hexagonal structure).
    Scans backend/app/modules/*/domain/ for entities, value_objects, repositories."""
    terms: list[DomainTerm] = []
    seen: set[str] = set()

    # Pattern: backend/app/modules/*/domain/{entities,value_objects,events}.py
    modules_root = project_dir / "backend" / "app" / "modules"
    if not modules_root.is_dir():
        return terms

    for mod_dir in sorted(modules_root.iterdir()):
        if not mod_dir.is_dir():
            continue
        domain_dir = mod_dir / "domain"
        if not domain_dir.is_dir():
            continue

        mod_name = mod_dir.name

        # ── entities.py / aggregates.py → Aggregate Root candidates ──
        for fname in ("entities.py", "aggregates.py", "aggregate_roots.py"):
            fpath = domain_dir / fname
            if not fpath.exists():
                continue
            text = _read(fpath)
            for cls_name, bases in _extract_classes_from_python(text):
                if cls_name in seen or cls_name.lower() in _STOP_WORDS:
                    continue
                # Skip enums, exceptions, mixins
                if any(x in bases for x in ("Enum", "Exception", "Error", "Mixin", "ABC", "Protocol")):
                    continue
                seen.add(cls_name)
                rel = f"{fpath.relative_to(project_dir)}:{cls_name}"
                terms.append(DomainTerm(
                    term=cls_name,
                    definition=f"Entidade de domínio em {mod_name}",
                    source=rel,
                    confidence="CONFIRMED",
                    kind="entity",
                ))

        # ── value_objects.py → Value Object candidates ──
        vo_path = domain_dir / "value_objects.py"
        if vo_path.exists():
            text = _read(vo_path)
            for cls_name, bases in _extract_classes_from_python(text):
                if cls_name in seen or cls_name.lower() in _STOP_WORDS:
                    continue
                if any(x in bases for x in ("Enum", "Exception", "Error")):
                    continue
                seen.add(cls_name)
                rel = f"{vo_path.relative_to(project_dir)}:{cls_name}"
                terms.append(DomainTerm(
                    term=cls_name,
                    definition=f"Value object em {mod_name}",
                    source=rel,
                    confidence="CONFIRMED",
                    kind="value_object",
                ))

        # ── events.py → Domain Event candidates ──
        ev_path = domain_dir / "events.py"
        if ev_path.exists():
            text = _read(ev_path)
            for cls_name, _ in _extract_classes_from_python(text):
                if cls_name in seen or cls_name.lower() in _STOP_WORDS:
                    continue
                seen.add(cls_name)
                rel = f"{ev_path.relative_to(project_dir)}:{cls_name}"
                terms.append(DomainTerm(
                    term=cls_name,
                    definition=f"Domain event em {mod_name}",
                    source=rel,
                    confidence="CONFIRMED",
                    kind="event",
                ))

        # ── repositories/ (port interfaces) ──
        repo_dir = domain_dir / "repositories"
        if repo_dir.is_dir():
            for fpath in sorted(repo_dir.glob("*.py")):
                if fpath.name == "__init__.py":
                    continue
                text = _read(fpath)
                for cls_name, bases in _extract_classes_from_python(text):
                    if cls_name in seen:
                        continue
                    seen.add(cls_name)
                    rel = f"{fpath.relative_to(project_dir)}:{cls_name}"
                    terms.append(DomainTerm(
                        term=cls_name,
                        definition=f"Repository (port) em {mod_name}",
                        source=rel,
                        confidence="CONFIRMED",
                        kind="repository",
                    ))

    return terms


def _extract_from_specs(data: dict) -> list[DomainTerm]:
    """Extract domain terms from specs — glossário sections and RF descriptions."""
    terms: list[DomainTerm] = []
    seen: set[str] = set()

    for spec in data.get("specs", []):
        spec_id = spec.get("id", "")
        spec_name = spec.get("name", "")
        spec_path = spec.get("specPath", "")

        # ── Module name as domain term ──
        if spec_name and spec_name not in seen:
            seen.add(spec_name)
            terms.append(DomainTerm(
                term=spec_name,
                definition=f"Módulo/bounded context {spec_id}",
                source=spec_path,
                confidence="CONFIRMED",
                kind="module",
            ))

        # ── RF descriptions — extract significant nouns ──
        for rf in spec.get("rfs", []):
            desc = rf.get("d", "")
            # Find backtick-quoted terms (explicit domain references)
            for m in re.finditer(r"`([A-Za-z][A-Za-z0-9_]{2,})`", desc):
                term = m.group(1)
                if term.lower() in _STOP_WORDS or term in seen:
                    continue
                # Only add if it looks like a domain term (not a file path)
                if "/" in term or "." in term:
                    continue
                seen.add(term)
                terms.append(DomainTerm(
                    term=term,
                    definition=f"Mencionado em {rf.get('id', '')} de {spec_id}",
                    source=f"{spec_path}:{rf.get('id', '')}",
                    confidence="INFERRED",
                    kind="glossary",
                ))

    return terms


def _extract_from_modules(data: dict) -> list[DomainTerm]:
    """Extract domain terms from module/code structure in the JSON."""
    terms: list[DomainTerm] = []
    seen: set[str] = set()

    for mod in data.get("modules", []):
        name = mod.get("name", "")
        if name and name not in seen:
            seen.add(name)
            terms.append(DomainTerm(
                term=name,
                definition=f"Módulo {mod.get('id', '')}",
                source=mod.get("modulePath", ""),
                confidence="CONFIRMED",
                kind="module",
            ))

    return terms


def _extract_acronyms(texts: list[str]) -> list[DomainTerm]:
    """Find acronyms/siglas (ALL-CAPS 2-6 chars) in a set of texts."""
    terms: list[DomainTerm] = []
    seen: set[str] = set()
    acronym_re = re.compile(r"\b([A-Z]{2,6})\b")

    for text in texts:
        for m in acronym_re.finditer(text):
            acr = m.group(1)
            # Filter common non-acronyms
            if acr in {"RF", "RNF", "ADR", "DDD", "UI", "UX", "API", "MCP",
                       "SQL", "JSON", "XML", "HTTP", "URL", "CSS", "HTML",
                       "SVG", "TDD", "BDD", "E2E", "PDF", "PPT", "CSV",
                       "UTF", "ISO", "CPF", "CNPJ", "CEP", "NCM", "SKU",
                       "SLA", "KPI", "OKR", "PR", "CI", "CD", "IO", "DB",
                       "ER", "FK", "PK", "AK", "IX", "UX", "DX", "OX"}:
                continue
            if acr in seen:
                continue
            seen.add(acr)
            terms.append(DomainTerm(
                term=acr,
                definition="Acrônimo/sigla encontrado no projeto",
                confidence="GAP",
                kind="acronym",
            ))

    return terms


def _extract_glossary_from_spec_text(project_dir: Path) -> list[DomainTerm]:
    """Extract terms from '## Glossário' or '## Linguagem Ubíqua' sections in specs."""
    terms: list[DomainTerm] = []
    seen: set[str] = set()

    specs_dir = project_dir / "specs"
    if not specs_dir.is_dir():
        return terms

    for spec_md in sorted(specs_dir.glob("*/spec.md")):
        text = _read(spec_md)
        # Find glossário / linguagem ubíqua section
        m = re.search(r"^##\s+(Gloss[áa]rio|Linguagem Ub[íi]qua|Ubiquitous Language)\s*$", text, re.M | re.I)
        if not m:
            continue
        start = m.end()
        next_h2 = re.search(r"^##\s+", text[start:], re.M)
        section = text[start:start + next_h2.start()] if next_h2 else text[start:]

        # Parse "- **Term**: definition" or "- Term: definition" patterns
        for line in section.splitlines():
            line = line.strip()
            if not line.startswith("-"):
                continue
            # Strip leading "- "
            line = line[2:].strip()
            # Match **Term**: def or Term: def
            m_term = re.match(r"\*{0,2}([^:*]{2,60})\*{0,2}\s*[:：]\s*(.+)", line)
            if m_term:
                term = m_term.group(1).strip().strip("*").strip()
                defn = m_term.group(2).strip()
                if term.lower() in _STOP_WORDS or term in seen:
                    continue
                seen.add(term)
                terms.append(DomainTerm(
                    term=term,
                    definition=defn[:200],
                    source=str(spec_md.relative_to(project_dir)),
                    confidence="CONFIRMED",
                    kind="glossary",
                ))

    return terms


# ──────────────────────────────────────────────────────────────────────
# 3. MAPPINGS — domain term → universal term
# ──────────────────────────────────────────────────────────────────────

def _build_mappings(domain_terms: list[DomainTerm]) -> list[Mapping]:
    """Map domain terms to universal terms using kind heuristics."""
    mappings: list[Mapping] = []

    for dt in domain_terms:
        if dt.kind == "entity":
            mappings.append(Mapping(
                domain_term=dt.term,
                universal_term="aggregate",
                confidence="CONFIRMED",
                reason="Entidade de domínio em domain/entities.py — raiz com invariantes",
            ))
        elif dt.kind == "value_object":
            mappings.append(Mapping(
                domain_term=dt.term,
                universal_term="aggregate",
                confidence="INFERRED",
                reason="Value object em domain/value_objects.py — parte de um aggregate root",
            ))
        elif dt.kind == "repository":
            mappings.append(Mapping(
                domain_term=dt.term,
                universal_term="port",
                confidence="CONFIRMED",
                reason="Repository (port) em domain/repositories/ — interface de domínio",
            ))
        elif dt.kind == "event":
            mappings.append(Mapping(
                domain_term=dt.term,
                universal_term="aggregate",
                confidence="INFERRED",
                reason="Domain event — emitido por um aggregate root",
            ))
        elif dt.kind == "module":
            mappings.append(Mapping(
                domain_term=dt.term,
                universal_term="module",
                confidence="CONFIRMED",
                reason="Módulo/bounded context com linguagem ubíqua própria",
            ))
        elif dt.kind == "glossary":
            # Glossary terms may map to features or RFs
            mappings.append(Mapping(
                domain_term=dt.term,
                universal_term="feature",
                confidence="INFERRED",
                reason="Termo de glossário — potencial feature ou conceito de domínio",
            ))
        elif dt.kind == "acronym":
            # Acronyms are GAP — we don't know what they map to
            mappings.append(Mapping(
                domain_term=dt.term,
                universal_term="artifact",
                confidence="GAP",
                reason="Acrônimo — mapeamento incerto, precisa de revisão humana",
            ))

    return mappings


# ──────────────────────────────────────────────────────────────────────
# 4. MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────────────

def build_taxonomy(data: dict, project_dir: str | Path | None = None) -> dict:
    """Build the full taxonomy: universal + domain + mappings.

    Args:
        data: JSON dict from generate.py/analyze.py.
        project_dir: Optional project root for code scanning.
                     If None, only extracts from the JSON data.

    Returns:
        {
            "categories": [...4 categories...],
            "universal_terms": [...15 terms...],
            "domain_terms": [...project-specific...],
            "mappings": [...domain→universal...],
            "summary": {counts...}
        }
    """
    project_path = Path(project_dir).resolve() if project_dir else None

    # ── Collect domain terms from all sources ──
    all_domain: list[DomainTerm] = []
    seen_terms: set[str] = set()

    def _add_terms(terms: list[DomainTerm]):
        for t in terms:
            if t.term not in seen_terms:
                seen_terms.add(t.term)
                all_domain.append(t)

    # Source 1: from code (if project_dir available)
    if project_path and project_path.is_dir():
        _add_terms(_extract_from_code(project_path))
        _add_terms(_extract_glossary_from_spec_text(project_path))

    # Source 2: from specs in JSON
    _add_terms(_extract_from_specs(data))

    # Source 3: from modules in JSON
    _add_terms(_extract_from_modules(data))

    # Source 4: acronyms from all available text
    texts_for_acronyms: list[str] = []
    for spec in data.get("specs", []):
        texts_for_acronyms.append(spec.get("name", ""))
        for rf in spec.get("rfs", []):
            texts_for_acronyms.append(rf.get("d", ""))
        for rnf in spec.get("rnfs", []):
            texts_for_acronyms.append(rnf.get("d", ""))
    for adr in data.get("adrs", []):
        texts_for_acronyms.append(adr.get("title", ""))
        texts_for_acronyms.append(adr.get("description", ""))
    _add_terms(_extract_acronyms(texts_for_acronyms))

    # ── Build mappings ──
    mappings = _build_mappings(all_domain)

    # ── Domain category ──
    domain_category = {"key": "domain", "label": "Domínio", "icon": "🏛️", "hint": "Termos ubíquos do domínio do projeto — extraídos de código, specs e glossário"}

    # ── Summary ──
    by_confidence = {"CONFIRMED": 0, "INFERRED": 0, "GAP": 0}
    by_kind: dict[str, int] = {}
    for dt in all_domain:
        by_confidence[dt.confidence] = by_confidence.get(dt.confidence, 0) + 1
        by_kind[dt.kind] = by_kind.get(dt.kind, 0) + 1

    return {
        "categories": UNIVERSAL_CATEGORIES + [domain_category],
        "universal_terms": UNIVERSAL_TERMS,
        "domain_terms": [asdict(dt) for dt in all_domain],
        "mappings": [asdict(m) for m in mappings],
        "summary": {
            "universal_count": len(UNIVERSAL_TERMS),
            "domain_count": len(all_domain),
            "mapping_count": len(mappings),
            "by_confidence": by_confidence,
            "by_kind": by_kind,
        },
    }


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build project-specific taxonomy from generate.py JSON output."
    )
    parser.add_argument("input", help="Path to JSON file from generate.py/analyze.py")
    parser.add_argument("--project-dir", "-p", help="Project root directory for code scanning")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    taxonomy = build_taxonomy(data, project_dir=args.project_dir)

    output = json.dumps(taxonomy, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Taxonomy written to {args.output}", file=sys.stderr)
        print(f"  Universal terms: {taxonomy['summary']['universal_count']}", file=sys.stderr)
        print(f"  Domain terms:    {taxonomy['summary']['domain_count']}", file=sys.stderr)
        print(f"  Mappings:        {taxonomy['summary']['mapping_count']}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
