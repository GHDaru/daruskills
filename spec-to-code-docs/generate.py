"""generate.py — Discovery + extraction module for spec-to-code-docs.

Scans a project directory and produces a JSON dict consumable by render.py.
Python 3.12+, stdlib only.

Usage:
    python generate.py <project_dir> [--output file.json]
    python generate.py D:/.../gestaodeprioridades

If --output is omitted, JSON is written to stdout.
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
    """Extract the first '# Heading' from markdown, stripping '# ' prefix."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _strip_emphasis(s: str) -> str:
    """Remove markdown emphasis (**bold**, *italic*, `code`) from a string."""
    return re.sub(r"`?\*{1,2}(.*?)\*{1,2}`?", r"\1", s).strip()


# ──────────────────────────────────────────────────────────────────────
# Specs
# ──────────────────────────────────────────────────────────────────────

def _extract_status(text: str) -> str:
    """Extract status from spec.md (e.g. '**Status**: **Aprovada**')."""
    m = re.search(r"Status\*?\*?:\s*\*{0,2}(Aprovada|Rascunho|Reprovada|Accepted|Rejected|Draft|Em curso|Concluída)\*{0,2}", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"Status\*?\*?:\s*\*{0,2}(\w+)\*{0,2}", text, re.I)
    if m:
        return m.group(1).strip()
    return ""


def _extract_artifacts(spec_dir: Path) -> list[dict]:
    """Find spec artifacts (plan.md, tasks.md, qa-report.md, retro.md, ux-design.md, etc)."""
    artifacts = []
    for f in sorted(spec_dir.iterdir()):
        if f.is_file() and f.suffix == ".md" and f.name != "spec.md":
            artifacts.append({"name": f.name, "path": str(f.relative_to(spec_dir.parent.parent))})
    # contracts/ subdir
    contracts = spec_dir / "contracts"
    if contracts.is_dir():
        for f in sorted(contracts.iterdir()):
            if f.is_file():
                artifacts.append({"name": f"contracts/{f.name}", "path": str(f.relative_to(spec_dir.parent.parent))})
    return artifacts


def _extract_requirements(text: str) -> tuple[list[dict], list[dict]]:
    """Extract RF and RNF requirements from spec text.
    Returns (rfs, rnfs) where each is [{id, d, s}].
    Looks for 'RF<n>' or 'RF-<n>' patterns and EARS syntax.
    """
    rfs = []
    rnfs = []

    # Pattern: **RF1**: ... or - **RF1**: ... or RF1: ...
    # Also: **RF1** — ... or - RF1: ...
    rf_pattern = re.compile(
        r"(?:^|\n)[-*\s]*\*{0,2}(RF[-]?\d+)\*{0,2}\s*[:：—–-]\s*(.+?)(?=\n[-*\s]*\*{0,2}R[FN]|\n##|\n###|\Z)",
        re.DOTALL,
    )
    rnf_pattern = re.compile(
        r"(?:^|\n)[-*\s]*\*{0,2}(RNF[-]?\d+)\*{0,2}\s*[:：—–-]\s*(.+?)(?=\n[-*\s]*\*{0,2}R[FN]|\n##|\n###|\Z)",
        re.DOTALL,
    )

    for m in rf_pattern.finditer(text):
        rid = m.group(1).replace("RF-", "RF")
        # Full description: join lines, strip markdown emphasis, truncate for display
        desc = m.group(2).strip()
        desc = re.sub(r"\s+", " ", desc)  # collapse whitespace/newlines
        desc = _strip_emphasis(desc)
        rfs.append({"id": rid, "d": desc, "s": ""})

    for m in rnf_pattern.finditer(text):
        rid = m.group(1).replace("RNF-", "RNF")
        desc = m.group(2).strip()
        desc = re.sub(r"\s+", " ", desc)
        desc = _strip_emphasis(desc)
        rnfs.append({"id": rid, "d": desc, "s": ""})

    return rfs, rnfs


def _extract_features(text: str) -> list[str]:
    """Extract feature names from spec (lines under '## Features' or similar)."""
    features = []
    in_features = False
    for line in text.splitlines():
        if re.match(r"^##\s*(Features|Funcionalidades|Escopo)", line, re.I):
            in_features = True
            continue
        if in_features and line.startswith("## "):
            break
        if in_features and line.strip().startswith("- "):
            feat = _strip_emphasis(line.strip()[2:])
            if feat:
                features.append(feat)
    return features


def _extract_vision(text: str) -> str:
    """Extract the first paragraph from '## O quê e por quê' (or '## Visão geral') section."""
    # Find the vision section heading
    m = re.search(r"^##\s+(O quê e por quê|Vis[ãa]o geral|Vis[ãa]o)\s*$", text, re.M | re.I)
    if not m:
        return ""
    start = m.end()
    # Find next ## heading
    next_h2 = re.search(r"^##\s+", text[start:], re.M)
    section = text[start:start + next_h2.start()] if next_h2 else text[start:]
    # First non-empty paragraph (skip blockquotes and blank lines)
    paragraphs = section.strip().split("\n\n")
    for para in paragraphs:
        para = para.strip()
        if para and not para.startswith(">") and not para.startswith("|"):
            # Take first 2-3 sentences max
            sentences = re.split(r"(?<=[.!?])\s+", para)
            vision = " ".join(sentences[:3])
            return _strip_emphasis(vision)
    return ""


def _extract_rf_sources(rf_text: str, spec_sources: list[dict]) -> str:
    """Extract source references from an RF's text. Falls back to spec-level sources."""
    refs = []
    # Find inline doc references
    for m in re.finditer(r"(docs/[a-z_]+/[a-z_-]+\.md|docs/[a-z_-]+\.md|prototipo/[a-z_./-]+|scripts/[a-z_.-]+)", rf_text):
        ref = m.group(1)
        # Shorten to just the filename for the source string
        tag = ref.split("/")[-1].replace(".md", "")
        if tag not in refs:
            refs.append(tag)
    if refs:
        return ", ".join(refs)
    # Fallback: use spec-level source tags
    if spec_sources:
        return ", ".join(s["tag"] for s in spec_sources[:3])
    return ""


def _extract_rf_subheadings(text: str) -> list[str] | None:
    """Extract ### sub-headings from within '## Requisitos funcionais' section.
    Returns list of heading texts, or None if no sub-headings found.
    """
    # Find the "## Requisitos funcionais" section
    m = re.search(r"^##\s+Requisitos funcionais\s*$", text, re.M | re.I)
    if not m:
        return None
    start = m.end()
    next_h2 = re.search(r"^##\s+", text[start:], re.M)
    section = text[start:start + next_h2.start()] if next_h2 else text[start:]
    # Find ### sub-headings
    subheadings = re.findall(r"^###\s+(.+?)$", section, re.M)
    if subheadings:
        return [_strip_emphasis(h.strip()) for h in subheadings]
    return None


def _semantic_fallback_name(chunk: list[dict], used_terms: set[str]) -> str:
    """Build a semantic feature name from RF text when domain terms are exhausted.
    Extracts the main verb (converted to noun) + main object.
    Example: 'O SISTEMA DEVE preservar o protótipo original...' → 'Preservação do protótipo'
    """
    verb_to_noun = {
        "preservar": "Preservação", "entregar": "Entrega", "declarar": "Declaração",
        "registrar": "Registro", "gerar": "Geração", "criar": "Criação",
        "extrair": "Extração", "fatiar": "Fatiamento", "exigir": "Exigência",
        "garantir": "Garantia", "recusar": "Recusa", "relatar": "Relato",
        "propor": "Proposição", "resolver": "Resolução", "conferir": "Conferência",
        "verificar": "Verificação", "examinar": "Exame", "executar": "Execução",
        "importar": "Importação", "validar": "Validação", "publicar": "Publicação",
        "monitorar": "Monitoramento", "processar": "Processamento", "calcular": "Cálculo",
        "aceitar": "Aceite", "rejeitar": "Rejeição", "bloquear": "Bloqueio",
        "proteger": "Proteção", "isolar": "Isolamento", "tratar": "Tratamento",
        "consumir": "Consumo", "carregar": "Carga", "apresentar": "Apresentação",
        "descrever": "Descrição", "definir": "Definição", "especificar": "Especificação",
    }
    # Nouns to look for as objects (domain-relevant)
    object_keywords = {
        "protótipo": "protótipo", "prototipo": "protótipo",
        "constituição": "constituição", "constitution": "constituição",
        "base": "base", "rounds": "rounds", "manifesto": "manifesto",
        "tema": "tema", "jornada": "jornada", "jornadas": "jornadas",
        "adaptador": "adaptador", "iframe": "iframe", "sandbox": "sandbox",
        "handshake": "handshake", "catálogo": "catálogo", "catalogo": "catálogo",
        "identidade": "identidade", "sessão": "sessão", "acao": "ação",
        "ação": "ação", "contrato": "contrato", "cenário": "cenário",
        "defeito": "defeito", "defeitos": "defeitos", "round": "round",
        "evidência": "evidência", "fitness": "fitness",
        "adr": "ADR", "ui": "UI", "ux": "UX",
    }

    all_text = " ".join(rf["d"] for rf in chunk).lower()

    # Find the first verb that's in our mapping
    verb_noun = None
    words = re.findall(r"[a-zà-ú]{4,}", all_text)
    for w in words:
        if w in verb_to_noun:
            verb_noun = verb_to_noun[w]
            break

    # Find the first domain object
    obj = None
    for w in words:
        if w in object_keywords:
            obj = object_keywords[w]
            break
    # Also check backtick refs for objects
    if not obj:
        backtick_refs = re.findall(r"`([^`]+)`", " ".join(rf["d"] for rf in chunk))
        for ref in backtick_refs:
            base = ref.lower().split("/")[-1].replace(".md", "").replace(".json", "").replace(".sh", "")
            if base in object_keywords:
                obj = object_keywords[base]
                break

    # Build name
    if verb_noun and obj:
        # Use "do/da" contraction
        article = "da" if obj.endswith("ão") or obj in ("base", "jornada", "jornadas", "ação", "sessão", "evidência", "constituição") else "do"
        return f"{verb_noun} {article} {obj}"
    elif verb_noun:
        return verb_noun
    elif obj:
        return obj.capitalize()
    else:
        # Last resort: use RF numbers without "Requisitos" prefix
        nums = [re.sub(r"[^\d]", "", rf["id"]) for rf in chunk]
        return f"RF {nums[0]}–{nums[-1]}"


def _group_rfs_into_features(rfs: list[dict], spec_text: str = "") -> list[dict]:
    """Group RFs into feature chunks with semantic names.
    Strategy:
    1. If spec has ### sub-headings in §3, use those as feature names.
    2. Otherwise, extract domain nouns from RF text (filter stop words + verbs + EARS).
    3. Fall back to "Requisitos X-Y".
    """
    if not rfs:
        return []

    # Strategy 1: check for author-given sub-headings
    subheadings = None
    if spec_text:
        subheadings = _extract_rf_subheadings(spec_text)
    if subheadings:
        # Map sub-headings to RF chunks
        chunk_size = max(1, len(rfs) // len(subheadings)) if subheadings else 3
        features = []
        for i, sh in enumerate(subheadings):
            start = i * chunk_size
            end = start + chunk_size if i < len(subheadings) - 1 else len(rfs)
            chunk = rfs[start:end]
            if chunk:
                features.append({
                    "n": sh,
                    "d": f"RFs {chunk[0]['id']}–{chunk[-1]['id']}",
                    "ep": 0, "t": 0,
                })
        if features:
            return features

    # Strategy 2: semantic noun extraction
    chunk_size = 3
    features = []

    # Comprehensive stop words + Portuguese verbs + EARS keywords
    stop_words = {
        # articles, prepositions, conjunctions, pronouns
        "o", "a", "os", "as", "de", "do", "da", "dos", "das", "e", "ou", "um", "uma",
        "no", "na", "nos", "nas", "por", "para", "com", "sem", "que", "não", "se", "em",
        "ao", "à", "às", "pelo", "pela", "pelas", "pelo", "este", "esta", "isso", "disso",
        "deste", "desta", "desse", "dessa", "aquele", "aquela", "cujo", "cuja", "qual",
        "quais", "como", "onde", "quando", "então", "assim", "mais", "menos", "já", "cada",
        "toda", "todo", "tudo", "nada", "algo", "algum", "alguma", "outro", "outra",
        "mesmo", "mesma", "próprio", "própria", "apenas", "sempre", "nunca", "também",
        "entre", "após", "antes", "durante", "até", "desde", "contra", "sob", "sobre",
        # EARS keywords
        "sistema", "deve", "devem", "quando", "if", "when", "then", "the", "system",
        "shall", "ento", "onde",
        # common Portuguese verbs (infinitive)
        "abrir", "apresentar", "entregar", "declarar", "registrar", "preservar", "gerar",
        "criar", "atualizar", "excluir", "resolver", "extrair", "fatiar", "mostrar",
        "consumir", "carregar", "recusar", "relatar", "propor", "aplicar", "existir",
        "tornar", "permitir", "bloquear", "exigir", "buscar", "ler", "escrever", "iniciar",
        "começar", "construir", "prototipar", "executar", "imprimir", "colar", "satisfazer",
        "produzir", "examinar", "verificar", "servir", "justificar", "ter", "ser", "estar",
        "ir", "fazer", "dizer", "ver", "dar", "passar", "ficar", "chegar", "saber",
        "poder", "querer", "dever", "haver", "andar", "cair", "pôr", "vir", "obter",
        "conter", "cobrir", "garantir", "reprovar", "trazer", "conferir", "confrontar",
        "devolver", "inventar", "admitir", "empurrar", "presumir", "ignorar", "mudar",
        "deixar", "ganhar", "perder", "atingir", "revelar", "reconciliar", "vestir",
        "subir", "tratar", "discutir", "decidir",
        # adjectives/adverbs that aren't domain terms
        "true", "false", "null", "seja", "devolve",
    }

    # Domain term mappings — backtick refs and keywords → clean names
    domain_map = {
        "claude.md": "Onboarding",
        "constitution": "Constituição",
        "constituição": "Constituição",
        "visao": "Visão de produto",
        "visão": "Visão de produto",
        "roadmap": "Roadmap",
        "rounds": "Rounds",
        "prototipo": "Protótipo",
        "protótipo": "Protótipo",
        "ux-design": "UX design",
        "ux-design.md": "UX design",
        "actionspec": "Catálogo de ações",
        "catálogo": "Catálogo de ações",
        "manifesto": "Manifesto",
        "manifesto.json": "Manifesto",
        "adaptador": "Adaptador",
        "tema": "Tema",
        "iframe": "iframe",
        "admissão": "Admissão",
        "defeitos": "Defeitos",
        "segurança": "Segurança",
        "evidência": "Evidência",
        "evidencia": "Evidência",
        "check-rounds": "Fitness",
        "check-rounds.sh": "Fitness",
        "new-cycle": "Ciclos",
        "new-cycle.sh": "Ciclos",
        "adr": "ADRs",
        "base": "Base real",
        "capturas": "Capturas",
        "jornada": "Jornadas",
        "jornadas": "Jornadas",
        "handshake": "Handshake",
        "introspect": "Introspecção",
        "postmessage": "postMessage",
        "sandbox": "Sandbox",
        "cookie": "Sessão",
        "tenant": "Tenant",
        "capability": "Capabilities",
    }

    used_terms: set[str] = set()  # track terms already used across features in this spec

    for i in range(0, len(rfs), chunk_size):
        chunk = rfs[i:i + chunk_size]
        rf_ids = f"RFs {chunk[0]['id']}–{chunk[-1]['id']}"

        # Collect all text from chunk RFs
        all_text = " ".join(rf["d"] for rf in chunk).lower()

        # Strategy 2a: check for domain terms via backtick refs
        found_terms = []
        # Directory-based semantic mapping for file paths
        dir_map = {
            "docs/prototipo": "Protótipo",
            "docs/integracao": "Integração",
            "docs/produto": "Visão de produto",
            "docs/governance": "Governança",
            "docs/adr": "ADRs",
            "scripts": "Scripts",
        }
        backtick_refs = re.findall(r"`([^`]+)`", " ".join(rf["d"] for rf in chunk))
        for ref in backtick_refs:
            ref_lower = ref.lower().strip()
            # Check directory-based mapping first
            dir_term = None
            for dir_prefix, term in dir_map.items():
                if dir_prefix in ref_lower:
                    dir_term = term
                    break
            # Extract base filename
            base_name = ref_lower.split("/")[-1].replace(".md", "").replace(".json", "").replace(".sh", "").replace(".tsx", "").replace(".ts", "")
            if base_name in domain_map:
                term = domain_map[base_name]
                if term not in found_terms:
                    found_terms.append(term)
            elif ref_lower in domain_map:
                term = domain_map[ref_lower]
                if term not in found_terms:
                    found_terms.append(term)
            elif dir_term and dir_term not in found_terms:
                found_terms.append(dir_term)
            elif "." in ref_lower and base_name not in stop_words and len(base_name) > 3 and base_name != "readme":
                term = base_name.capitalize()
                if term not in found_terms:
                    found_terms.append(term)

        # Strategy 2b: check for high-signal domain keywords (only unambiguous ones)
        high_signal_keywords = {
            "constituição": "Constituição", "constitution": "Constituição",
            "protótipo": "Protótipo", "prototipo": "Protótipo",
            "ux-design": "UX design",
            "actionspec": "Catálogo de ações", "catálogo": "Catálogo de ações",
            "manifesto": "Manifesto",
            "adaptador": "Adaptador",
            "admissão": "Admissão",
            "defeitos": "Defeitos",
            "evidência": "Evidência", "evidencia": "Evidência",
            "jornada": "Jornadas", "jornadas": "Jornadas",
            "handshake": "Handshake",
            "introspect": "Introspecção",
            "postmessage": "postMessage",
            "sandbox": "Sandbox",
            "rounds": "Rounds",
            "roadmap": "Roadmap",
            "adr": "ADRs",
            "base real": "Base real",
            "identidade": "Identidade",
            "iframe": "iframe",
            "capturas": "Capturas",
            "tema próprio": "Tema",
        }
        for keyword, term in high_signal_keywords.items():
            if keyword in all_text and term not in found_terms:
                found_terms.append(term)

        # Strategy 2c: extract remaining significant nouns
        if not found_terms:
            words = re.findall(r"[A-Za-zà-úÀ-Ú]{4,}", all_text)
            significant = [w for w in words if w.lower() not in stop_words]
            # Take first 2 unique significant words
            seen = set()
            for w in significant:
                wl = w.lower()
                if wl not in seen:
                    seen.add(wl)
                    found_terms.append(w.capitalize())
                if len(found_terms) >= 2:
                    break

        # Deduplicate: remove terms already used in previous features of this spec
        found_terms = [t for t in found_terms if t not in used_terms]

        # Build feature name
        if found_terms:
            # Normalize order: sort alphabetically for consistency
            terms_sorted = sorted(found_terms[:2], key=str.lower)
            name = " e ".join(terms_sorted)
            # Mark these terms as used
            used_terms.update(found_terms[:2])
        else:
            # Strategy 3: semantic fallback — verb→noun + object from RF text
            name = _semantic_fallback_name(chunk, used_terms)

        features.append({
            "n": name,
            "d": rf_ids,
            "ep": 0, "t": 0,
        })
    return features


def _extract_sources(text: str, project: Path) -> list[dict]:
    """Extract source references from spec text (docs/, prototipo/, scripts/ paths)."""
    sources = []
    seen = set()
    # Find referenced paths: docs/governance/X.md, docs/produto/X.md, prototipo/X, scripts/X.sh
    for m in re.finditer(r"(docs/[a-z_]+/[a-z_-]+\.md|docs/[a-z_-]+\.md|prototipo/[a-z_./-]+|scripts/[a-z_.-]+)", text):
        ref = m.group(1)
        if ref in seen:
            continue
        seen.add(ref)
        # Verify the file exists
        full = project / ref
        if not full.exists():
            continue
        # Generate a tag and description
        parts = ref.split("/")
        if "governance" in ref:
            tag = parts[-1].replace(".md", "")
            desc = f"Constituição/governança: {tag}"
        elif "produto" in ref:
            tag = parts[-1].replace(".md", "")
            desc = f"Documento de produto: {tag}"
        elif "adr" in ref:
            tag = parts[-1].replace(".md", "")
            desc = f"ADR: {tag}"
        elif "prototipo" in ref:
            tag = "/".join(parts[1:])
            desc = "Protótipo navegável"
        elif "scripts" in ref:
            tag = parts[-1]
            desc = "Script de verificação/fitness"
        else:
            tag = parts[-1]
            desc = ref
        sources.append({"tag": tag, "desc": desc, "path": ref})
    return sources


def extract_rnfs_from_constitution(project: Path) -> list[dict]:
    """Extract P1-P7 principles from docs/governance/constitution.md as RNFs."""
    text = _read(project / "docs" / "governance" / "constitution.md")
    rnfs = []
    # Pattern: ### P1. Title (INEGOCIÁVEL) or ### P1. Title
    for m in re.finditer(r"^###\s+(P\d+)\.\s+(.+?)(?:\s*\((INEGOCIÁVEL|negociável)\))?\s*$", text, re.M | re.I):
        rid = m.group(1)
        title = _strip_emphasis(m.group(2).strip())
        negotiable = m.group(3) or ""
        # Extract first paragraph after the heading as description
        start = m.end()
        next_heading = re.search(r"^###\s+", text[start:], re.M)
        if next_heading:
            body = text[start:start + next_heading.start()].strip()
        else:
            body = text[start:].strip()
        # First paragraph
        first_para = body.split("\n\n")[0].strip() if body else ""
        first_para = _strip_emphasis(first_para[:200])
        desc = f"{title}"
        if negotiable:
            desc += f" ({negotiable})"
        if first_para:
            desc += f" — {first_para}"
        rnfs.append({"id": rid, "d": desc, "s": "docs/governance/constitution.md"})
    return rnfs


def _build_fwd_map(spec: dict, project: Path) -> tuple[list[dict], list[dict]]:
    """Build approximate forward map: RF → spec → plan → prototipo → teste.
    Returns (fwdMap, rnfFwdMap).
    """
    spec_dir = (project / spec["specPath"]).parent
    has_plan = (spec_dir / "plan.md").exists()
    has_tasks = (spec_dir / "tasks.md").exists()
    has_qa = (spec_dir / "qa-report.md").exists()
    has_proto = (project / "prototipo" / "index.html").exists()

    # Build chain artifacts
    chain = []
    if has_plan:
        chain.append("plan.md")
    if has_tasks:
        chain.append("tasks.md")
    if has_proto:
        chain.append("prototipo")
    if has_qa:
        chain.append("qa-report.md")

    # Map all RFs to the same chain (approximate — no per-RF granularity)
    fwd_map = []
    if spec["rfs"] and chain:
        first_rf = int(re.sub(r"[^\d]", "", spec["rfs"][0]["id"]) or "1")
        last_rf = int(re.sub(r"[^\d]", "", spec["rfs"][-1]["id"]) or str(first_rf))
        entry = {"rf": [first_rf, last_rf], "tela": "", "ep": "", "test": "", "ac": " → ".join(chain)}
        fwd_map.append(entry)

    rnf_fwd_map = []
    if spec["rnfs"]:
        first_rnf = int(re.sub(r"[^\d]", "", spec["rnfs"][0]["id"]) or "1")
        last_rnf = int(re.sub(r"[^\d]", "", spec["rnfs"][-1]["id"]) or str(first_rnf))
        entry = {"rf": [first_rnf, last_rnf], "tela": "", "ep": "", "test": "", "ac": " → ".join(chain) if chain else ""}
        rnf_fwd_map.append(entry)

    return fwd_map, rnf_fwd_map


def discover_specs(project: Path, constitution_rnfs: list[dict] | None = None) -> list[dict]:
    """Discover all specs in specs/*/spec.md."""
    specs = []
    spec_dirs = sorted(project.glob("specs/*/spec.md"))
    for spec_md in spec_dirs:
        text = _read(spec_md)
        spec_dir = spec_md.parent
        spec_id = spec_dir.name
        title = _first_line_heading(text) or spec_id
        status = _extract_status(text)
        artifacts = _extract_artifacts(spec_dir)
        rfs, rnfs = _extract_requirements(text)
        features = _extract_features(text)
        sources = _extract_sources(text, project)
        vision = _extract_vision(text)

        # Assign sources to each RF
        for rf in rfs:
            rf["s"] = _extract_rf_sources(rf["d"], sources)

        # Merge constitution RNFs (P1-P7) into each spec's RNFs
        if constitution_rnfs:
            existing_rnf_ids = {r["id"] for r in rnfs}
            for crnf in constitution_rnfs:
                if crnf["id"] not in existing_rnf_ids:
                    rnfs.append(crnf)

        # If no features extracted from ## Features, group RFs into feature chunks
        if not features:
            features = _group_rfs_into_features(rfs, text)

        specs.append({
            "id": spec_id,
            "name": title,
            "titulo": title,
            "status": status,
            "artifacts": artifacts,
            "rfs": rfs,
            "rnfs": rnfs,
            "rf": len(rfs),
            "features": features,
            "ac": [],
            "specDir": spec_id,
            "specNum": spec_id.split("-")[0] if "-" in spec_id else spec_id,
            "specPath": str(spec_md.relative_to(project)),
            "description": title,
            "vision": vision,
            "deps": "",
            "color": "#5b5bd6",
            "transversal": False,
            "endpoints": 0,
            "tools": 0,
            "telas": 0,
            "testes": 0,
            "backend": "",
            "frontend": "",
            "sources": sources,
        })
    return specs


# ──────────────────────────────────────────────────────────────────────
# ADRs
# ──────────────────────────────────────────────────────────────────────

def discover_adrs(project: Path) -> list[dict]:
    """Discover ADRs in docs/adr/*.md."""
    adrs = []
    adr_files = sorted(project.glob("docs/adr/*.md"))
    for f in adr_files:
        if f.name == "README.md":
            continue
        text = _read(f)
        title = _first_line_heading(text)
        # Extract ADR number from filename or title
        m = re.search(r"(\d+)", f.name)
        n = m.group(1) if m else ""
        # Also try title: "ADR 0001 — ..."
        if not n:
            m2 = re.search(r"ADR\s*(\d+)", title)
            n = m2.group(1) if m2 else ""

        # Extract status
        status = ""
        m_status = re.search(r"Status\*?\*?:\s*\*{0,2}(\w+)\*{0,2}", text, re.I)
        if m_status:
            status = m_status.group(1).strip()

        # Extract title without "ADR N — " prefix
        clean_title = re.sub(r"^ADR\s*\d+\s*[—–\-]\s*", "", title).strip() or title

        # Extract first paragraph after "## Contexto" as context
        context = ""
        ctx_match = re.search(r"##\s*Contexto\s*\n(.+?)(?=\n##|\Z)", text, re.DOTALL)
        if ctx_match:
            context = ctx_match.group(1).strip().split("\n\n")[0].strip()

        # Extract decision summary
        description = ""
        dec_match = re.search(r"##\s*Decis[ãa]o\s*\n(.+?)(?=\n##|\Z)", text, re.DOTALL)
        if dec_match:
            description = dec_match.group(1).strip().split("\n\n")[0].strip()

        adrs.append({
            "n": n,
            "title": clean_title,
            "status": status,
            "description": description,
            "context": context,
        })
    return adrs


# ──────────────────────────────────────────────────────────────────────
# Skills
# ──────────────────────────────────────────────────────────────────────

def discover_skills(project: Path) -> list[dict]:
    """Discover skills in skills/*/SKILL.md or skills/*/skill.md."""
    skills = []
    skill_files = sorted(project.glob("skills/*/SKILL.md"))
    if not skill_files:
        skill_files = sorted(project.glob("skills/*/skill.md"))
    for f in skill_files:
        text = _read(f)
        # Parse frontmatter
        name = f.parent.name
        description = ""
        if text.startswith("---"):
            fm_end = text.find("---", 3)
            if fm_end > 0:
                fm = text[3:fm_end]
                m_name = re.search(r"^name:\s*(.+)$", fm, re.M)
                if m_name:
                    name = m_name.group(1).strip()
                m_desc = re.search(r"^description:\s*(.+)$", fm, re.M)
                if m_desc:
                    description = m_desc.group(1).strip()
        skills.append({
            "name": name,
            "description": description,
            "path": str(f.relative_to(project)),
        })
    return skills


# ──────────────────────────────────────────────────────────────────────
# Scripts
# ──────────────────────────────────────────────────────────────────────

def discover_scripts(project: Path) -> list[dict]:
    """Discover scripts in scripts/*."""
    scripts = []
    scripts_dir = project / "scripts"
    if not scripts_dir.is_dir():
        return scripts
    for f in sorted(scripts_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            ext = f.suffix.lower()
            type_map = {".py": "Python", ".sh": "Bash", ".mjs": "Node", ".js": "Node"}
            scripts.append({
                "name": f.name,
                "description": "",
                "type": type_map.get(ext, ext.lstrip(".") or "file"),
            })
    return scripts


# ──────────────────────────────────────────────────────────────────────
# Jornadas
# ──────────────────────────────────────────────────────────────────────

def discover_jornadas(project: Path) -> list[dict]:
    """Discover jornadas in docs/jornadas/*.md."""
    journeys = []
    j_files = sorted(project.glob("docs/jornadas/*.md"))
    for f in j_files:
        text = _read(f)
        title = _first_line_heading(text) or f.stem
        # Count steps: look for "## Passo N", "### N.", or "## " sections (excluding first heading)
        steps = len(re.findall(r"^##\s+Passo\s+\d+", text, re.M))
        if not steps:
            steps = len(re.findall(r"^###\s+\d+\.", text, re.M))
        if not steps:
            # Count "## " sections minus the first heading
            h2_sections = len(re.findall(r"^##\s+", text, re.M))
            steps = max(0, h2_sections - 1) if h2_sections > 1 else 0
        journeys.append({
            "id": f.stem,
            "name": title,
            "description": "",
            "steps": steps,
        })
    return journeys


# ──────────────────────────────────────────────────────────────────────
# Prototype
# ──────────────────────────────────────────────────────────────────────

def discover_prototype(project: Path) -> dict | None:
    """Discover prototype in prototipo/."""
    proto = project / "prototipo"
    if not proto.is_dir():
        return None
    index = proto / "index.html"
    return {
        "name": "Protótipo navegável",
        "description": "HTML/JS descartável (ADR 0005), não é código de produção.",
        "path": str(index.relative_to(project)) if index.exists() else str(proto.relative_to(project)),
    }


# ──────────────────────────────────────────────────────────────────────
# Visão geral (overview)
# ──────────────────────────────────────────────────────────────────────

def extract_stack(project: Path) -> dict:
    """Extract stack info from ADR 0002 or CLAUDE.md."""
    # Try ADR 0002 first
    adr_files = list(project.glob("docs/adr/0002*.md"))
    text = ""
    for f in adr_files:
        text = _read(f)
        if text:
            break
    if not text:
        text = _read(project / "CLAUDE.md")

    text_lower = text.lower()

    stack = {
        "frontend": "",
        "backend": "",
        "banco": "",
        "storage": "",
        "observability": "",
        "deploy": "",
    }

    if "react" in text_lower:
        stack["frontend"] = "React"
    if "fastapi" in text_lower:
        stack["backend"] = "FastAPI (Python)"
    elif "python" in text_lower and "fast" in text_lower:
        stack["backend"] = "FastAPI (Python)"
    if "postgres" in text_lower:
        if "neon" in text_lower:
            stack["banco"] = "PostgreSQL Neon"
        else:
            stack["banco"] = "PostgreSQL"
    if "s3" in text_lower or "backblaze" in text_lower:
        parts = []
        if "s3" in text_lower:
            parts.append("S3")
        if "backblaze" in text_lower or "b2" in text_lower:
            parts.append("Backblaze B2")
        stack["storage"] = " (".join(parts[:1]) + (f" ({parts[1]})" if len(parts) > 1 else "")
        if not stack["storage"]:
            stack["storage"] = "S3"
    if "opentelemetry" in text_lower:
        stack["observability"] = "OpenTelemetry"
    # Deploy: check ADR 0018 or text for Vercel/Railway
    adr18 = list(project.glob("docs/adr/0018*.md"))
    deploy_text = text_lower
    for f in adr18:
        deploy_text = _read(f).lower()
        if deploy_text:
            break
    deploy_parts = []
    if "vercel" in deploy_text:
        deploy_parts.append("Vercel")
    if "railway" in deploy_text:
        deploy_parts.append("Railway")
    if deploy_parts:
        stack["deploy"] = " + ".join(deploy_parts)

    return stack


def extract_overview(project: Path, specs: list[dict]) -> dict:
    """Extract overview from CLAUDE.md / README.md."""
    text = _read(project / "CLAUDE.md") or _read(project / "README.md")

    # First heading as title
    title = _first_line_heading(text) or project.name

    # First blockquote or first paragraph as lede
    lede = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") and stripped != ">":
            lede += stripped.lstrip("> ").strip() + " "
        elif lede and not stripped.startswith(">"):
            break
    lede = lede.strip() or "Projeto em pré-implementação."

    # Build cards from specs
    cards = []
    for s in specs:
        cards.append({
            "title": s["id"],
            "content": f"{s['name']} — {s['status'] or 'sem status'} · {s['rf']} RFs",
        })

    return {
        "eyebrow": "Visão geral",
        "title": title,
        "lede": lede,
        "cards": cards,
    }


# ──────────────────────────────────────────────────────────────────────
# Roadmap
# ──────────────────────────────────────────────────────────────────────

def extract_roadmap(project: Path, specs: list[dict]) -> dict:
    """Extract roadmap from docs/roadmap.md or specs/003-*/spec.md."""
    rm_text = _read(project / "docs" / "roadmap.md")
    if not rm_text:
        for s in specs:
            if "roadmap" in s["id"].lower() or "003" in s["id"]:
                rm_text = _read(project / s["specPath"])
                break

    # Parse cycle table: | **001** | Nome | Entrega | Raia |
    cycles = []
    for m in re.finditer(r"\|\s*\*{0,2}(\d+\+?)\*{0,2}\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", rm_text):
        if m.group(1) == "Ciclo":
            continue
        cycles.append({
            "num": m.group(1),
            "name": _strip_emphasis(m.group(2)),
            "entrega": _strip_emphasis(m.group(3)),
            "raia": _strip_emphasis(m.group(4)),
        })

    # Extract gates from cycle sections (## Ciclo NNN — ...)
    cycle_gates: dict[str, list[str]] = {}
    for m in re.finditer(r"^##\s+Ciclo\s+(\d+\+?)\s*[—–-]\s*(.+?)$", rm_text, re.M):
        cnum = m.group(1)
        section_start = m.end()
        next_section = re.search(r"^##\s+", rm_text[section_start:], re.M)
        section_text = rm_text[section_start:section_start + next_section.start()] if next_section else rm_text[section_start:]
        # Look for gate-like content: bullet points with criteria (skip strikethrough and bold-only items)
        gates = []
        for line in section_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- ") and not stripped.startswith("- ~~") and not stripped.startswith("- **~~"):
                gate_text = _strip_emphasis(stripped[2:])
                if gate_text and len(gate_text) > 5 and not gate_text.startswith("~~"):
                    gates.append(gate_text)
        if gates:
            cycle_gates[cnum] = gates

    # Extract dependencies from "### O que o ciclo 004 **não pode** começar sem"
    dependencies = []
    dep_match = re.search(r"###\s+O que o ciclo\s*(\d+\+?)\s*\*{0,2}n[ãa]o pode\*{0,2}\s*come[çc]ar sem", rm_text, re.I)
    if dep_match:
        dep_ciclo = dep_match.group(1)
        section_start = dep_match.end()
        next_section = re.search(r"^##\s+", rm_text[section_start:], re.M)
        section_text = rm_text[section_start:section_start + next_section.start()] if next_section else rm_text[section_start:]
        for line in section_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                # Skip strikethrough (superseded) items
                if stripped.startswith("- ~~") or stripped.startswith("- **~~"):
                    continue
                dep_text = _strip_emphasis(stripped[2:])
                if dep_text and len(dep_text) > 5:
                    dependencies.append({
                        "from": f"Ciclo {dep_ciclo}",
                        "to": [dep_text[:80]],
                        "why": "Pré-requisito de entrada",
                    })

    # Build bands from cycles
    bands = [{
        "title": "Ciclos",
        "tag": "MAESTRO",
        "sub": "Sequência de ciclos com gates",
        "cycles": [
            {
                "num": c["num"],
                "title": c["name"],
                "mod": "",
                "desc": c["entrega"],
                "cls": "demo" if c["num"] in ("001", "002", "003") else "infra",
                "meta": [{"cls": "ok", "text": c["raia"]}],
                "artifacts": [],
                "gates": [{"text": g[:60]} for g in cycle_gates.get(c["num"], [])],
            }
            for c in cycles
        ],
    }]

    return {
        "eyebrow": "Roadmap",
        "title": "Roadmap de ciclos",
        "lede": "Sequência de ciclos do método MAESTRO. Nenhuma linha de código de produção nasce antes do ciclo 004.",
        "callout": "Cada ciclo tem gates de entrada e saída. Gate vermelho → volta ao ciclo anterior.",
        "metrics": [],
        "horizons": [
            {"cls": "done", "label": "Done", "title": "Ciclos 001–003", "items": [c["name"] for c in cycles if c["num"] in ("001", "002", "003")]},
            {"cls": "now", "label": "Now", "title": "Próximo ciclo", "items": ["Implementação (004+)"]},
            {"cls": "later", "label": "Later", "title": "Depois", "items": ["Federação", "Observabilidade", "Deploy"]},
        ],
        "phases": [],
        "dependencies": dependencies,
        "legend": [
            {"cls": "", "label": "Ciclo concluído"},
            {"cls": "fix", "label": "Gate vermelho"},
            {"cls": "demo", "label": "Protótipo"},
            {"cls": "infra", "label": "Infra"},
        ],
        "bands": bands,
        "honesty": "O roadmap é uma sequência, não uma promessa de data.",
        "footer": "",
    }


# ──────────────────────────────────────────────────────────────────────
# Traceability
# ──────────────────────────────────────────────────────────────────────

def build_traceability(specs: list[dict], project: Path) -> dict:
    """Build traceability data from specs with sources and forward maps."""
    modules = []
    for s in specs:
        fwd_map, rnf_fwd_map = _build_fwd_map(s, project)
        modules.append({
            "id": s["specNum"],
            "name": s["name"],
            "specNum": s["specNum"],
            "specPath": s["specPath"],
            "modulePath": "",
            "frontend": "",
            "backend": "",
            "rfs": s["rfs"],
            "rnfs": s["rnfs"],
            "sources": s.get("sources", []),
            "fwdMap": fwd_map,
            "rnfFwdMap": rnf_fwd_map,
        })
    return {"modules": modules}


# ──────────────────────────────────────────────────────────────────────
# Taxonomy (best-effort from specs)
# ──────────────────────────────────────────────────────────────────────

def build_taxonomy(specs: list[dict]) -> dict:
    """Build a minimal taxonomy from spec content."""
    terms = []
    for s in specs:
        for rf in s["rfs"]:
            terms.append({
                "term": rf["id"],
                "id": s["specNum"],
                "def": rf["d"],
                "map": f"Spec {s['id']}",
                "analogy": "",
                "cat": "rf",
            })
    return {
        "categories": [
            {"key": "rf", "label": "Requisitos funcionais", "icon": "📋", "hint": "EARS syntax"},
        ],
        "terms": terms,
        "lede": "Termos de domínio extraídos das specs.",
        "callout": "Cada requisito segue a sintaxe EARS (WHEN <condition> THE SYSTEM SHALL <behavior>).",
    }


# ──────────────────────────────────────────────────────────────────────
# Workflow (best-effort)
# ──────────────────────────────────────────────────────────────────────

def build_workflow() -> dict:
    """Build a minimal workflow from MAESTRO phases."""
    return {
        "lede": "Workflow reproduzível do método MAESTRO.",
        "callout": "Cada fase tem critérios de entrada (gate) e saída (verificável).",
        "phases": [
            {"n": "I", "title": "Spec", "icon": "📝", "owner": "Product Steward", "goal": "Especificação como fonte de verdade", "entrada": ["Problema definido"], "saida": ["spec.md"], "metric": "# requisitos", "fail": {"to": "I", "action": "Reescrever spec"}},
            {"n": "II", "title": "Plan", "icon": "🗺️", "owner": "Tech Lead", "goal": "Plano de execução", "entrada": ["spec.md aprovada"], "saida": ["plan.md", "tasks.md"], "metric": "# tasks", "fail": {"to": "I", "action": "Voltar à spec"}},
            {"n": "III", "title": "Build", "icon": "🔨", "owner": "Agentes", "goal": "Implementação", "entrada": ["plan.md aprovado"], "saida": ["código", "testes"], "metric": "coverage", "fail": {"to": "II", "action": "Revisar plano"}},
            {"n": "IV", "title": "QA", "icon": "✅", "owner": "Crítico", "goal": "Verificação", "entrada": ["Build pronto"], "saida": ["qa-report.md"], "metric": "# findings", "fail": {"to": "III", "action": "Rework"}},
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def generate(project_dir: str | Path) -> dict:
    """Generate the full JSON data dict from a project directory."""
    project = Path(project_dir).resolve()

    constitution_rnfs = extract_rnfs_from_constitution(project)
    specs = discover_specs(project, constitution_rnfs)
    adrs = discover_adrs(project)
    skills = discover_skills(project)
    scripts = discover_scripts(project)
    journeys = discover_jornadas(project)
    prototype = discover_prototype(project)
    overview = extract_overview(project, specs)
    stack = extract_stack(project)
    roadmap = extract_roadmap(project, specs)
    traceability = build_traceability(specs, project)
    taxonomy = build_taxonomy(specs)
    workflow = build_workflow()

    # Count metrics
    total_rfs = sum(s["rf"] for s in specs)
    total_rnfs = sum(len(s["rnfs"]) for s in specs)
    metrics = [
        ["Specs", str(len(specs))],
        ["ADRs", str(len(adrs))],
        ["Skills", str(len(skills))],
        ["Scripts", str(len(scripts))],
        ["Jornadas", str(len(journeys))],
        ["Requisitos funcionais", str(total_rfs)],
        ["Requisitos não-funcionais", str(total_rnfs)],
        ["Total de requisitos", str(total_rfs + total_rnfs)],
    ]

    # Project metadata
    claude_text = _read(project / "CLAUDE.md")
    project_name = _first_line_heading(claude_text) or project.name

    data = {
        "project": {
            "name": project_name,
            "subtitle": "Pré-implementação",
            "lang": "pt-BR",
            "gauntlet": "—",
        },
        "overview": overview,
        "taxonomy": taxonomy,
        "workflow": workflow,
        "adrs": adrs,
        "metrics": metrics,
        "modules": [],
        "specs": specs,
        "skills": skills,
        "scripts": scripts,
        "journeys": journeys,
        "prototype": prototype,
        "stack": stack,
        "traceability": traceability,
        "roadmap": roadmap,
    }
    return data


def main():
    parser = argparse.ArgumentParser(description="Generate JSON data from a project directory for spec-to-code-docs.")
    parser.add_argument("project", help="Path to the project directory")
    parser.add_argument("--output", "-o", help="Output JSON file path (default: stdout)")
    args = parser.parse_args()

    data = generate(args.project)
    output = json.dumps(data, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"JSON written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
