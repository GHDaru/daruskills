"""render.py — HTML renderer for spec-to-code-docs.

Takes a JSON data dict (from generate.py) and produces a navigable
documentation site: index.html, modules.html, traceability.html,
roadmap.html, styles.css.

Python 3.12+, stdlib only. No external dependencies.

Usage:
    import render
    render.render(data, "docs/product-site")

Or CLI:
    python render.py input.json --output docs/product-site
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from html import escape

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />'
)

# SVG icons — monochromatic, stroke=currentColor, 16px in sidebar
_ICONS = {
    "overview": '<svg viewBox="0 0 24 24"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M9 12h6"/><path d="M9 16h4"/></svg>',
    "taxonomy": '<svg viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><circle cx="7" cy="7" r="1"/></svg>',
    "roadmap": '<svg viewBox="0 0 24 24"><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h6a4 4 0 0 0 4-4V7"/></svg>',
    "modules": '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
    "traceability": '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
    "workflow": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>',
    "adrs": '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h6"/></svg>',
    "metrics": '<svg viewBox="0 0 24 24"><path d="M3 21h18"/><path d="M7 21V13"/><path d="M13 21V8"/><path d="M19 21V4"/></svg>',
    "skills": '<svg viewBox="0 0 24 24"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>',
    "scripts": '<svg viewBox="0 0 24 24"><path d="M4 17l6-6-6-6"/><path d="M12 19h8"/></svg>',
    "journeys": '<svg viewBox="0 0 24 24"><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h6a4 4 0 0 0 4-4V7"/><path d="M6 17V9a4 4 0 0 1 4-4h4"/></svg>',
    "prototype": '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>',
    "artifacts": '<svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96L12 12.01l8.73-5.05"/><path d="M12 22.08V12"/></svg>',
}

_MOON_SVG = '<svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'
_SUN_SVG = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'

# ── Default taxonomy — 15 fixed terms in 3 categories (from reference site) ──
_DEFAULT_TAXONOMY_CATEGORIES = [
    {"key": "produto", "label": "Produto", "icon": "📦", "hint": "Épico ⊃ Feature ⊃ Story — a hierarquia de valor de negócio"},
    {"key": "engenharia", "label": "Engenharia", "icon": "⚙️", "hint": "Módulo, Spec, ADR, DDD/Hexagonal — a estrutura técnica"},
    {"key": "metodologia", "label": "Metodologia", "icon": "📋", "hint": "Gauntlet, Jornada — como trabalhamos"},
]

_DEFAULT_TAXONOMY_TERMS = [
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

_THEME_SCRIPT = """\
<script>
const tt=document.getElementById("themeToggle");
const MOON_SVG='{moon}';
const SUN_SVG='{sun}';
function applyTheme(t){{document.documentElement.setAttribute("data-theme",t);tt.innerHTML=t==="dark"?SUN_SVG:MOON_SVG;try{{localStorage.setItem("ecs-theme",t);}}catch(e){{}}}}
tt.addEventListener("click",()=>applyTheme(document.documentElement.getAttribute("data-theme")==="dark"?"light":"dark"));
try{{const saved=localStorage.getItem("ecs-theme");if(saved)applyTheme(saved);else applyTheme("light");}}catch(e){{}}
</script>""".format(moon=_MOON_SVG, sun=_SUN_SVG)


# ── Default workflow — 7 phases (0-6) from reference site ──
_DEFAULT_WORKFLOW_PHASES = [
    {"n": 0, "title": "Setup", "icon": "🔧", "goal": "Estruturar repo, git, CLAUDE.md, esqueleto MAESTRO.", "owner": "Gerente", "metric": "git log ≥1 commit; CLAUDE.md referencia PROJECT_OVERVIEW", "entrada": ["Documentação legada disponível"], "saida": ["Repo git versionado", "CLAUDE.md carrega PROJECT_OVERVIEW.md", "Estrutura backend/ + frontend/"], "fail": {"to": 0, "action": "Repo sem CLAUDE.md → criar do template MAESTRO"}},
    {"n": 1, "title": "Inventário & Extração", "icon": "📚", "goal": "Ler TODA a documentação legada e extrair entidades, fluxos, telas, regras de negócio.", "owner": "Worker especialista", "metric": "tabelas/fluxos mapeados; glossário cobre termos do spec", "entrada": ["Repo versionado com CLAUDE.md"], "saida": ["Tabelas catalogadas", "Glossário de termos versionado", "Fluxos de negócio extraídos"], "fail": {"to": 1, "action": "Inventário incompleto → extrair mais docs legadas até tabelas/fluxos mapeados"}},
    {"n": 2, "title": "Requisitos (Specs)", "icon": "📝", "goal": "Para cada módulo, escrever spec.md — a fonte de verdade. 10 seções padronizadas.", "owner": "Gerente aprova", "metric": "§3 RF ≥1 por fluxo; §4 RNF cobre perf/seg/i18n/a11y; §9 cada RF cita doc legada", "entrada": ["Inventário completo", "Glossário versionado"], "saida": ["specs/NNN-*/spec.md", "§3 RF + §4 RNF por módulo", "§9 Fontes consultadas (rastreabilidade)"], "fail": {"to": 1, "action": "Gap de spec → voltar ao inventário, extrair mais docs legadas"}},
    {"n": 3, "title": "Plan & Tasks", "icon": "🗂️", "goal": "Decompor cada spec em plano técnico e tarefas executáveis.", "owner": "Worker especialista", "metric": "Toda tarefa em tasks.md rastreia a um RF/RNF da spec", "entrada": ["spec.md aprovado"], "saida": ["plan.md com decisões técnicas + ADRs", "tasks.md com checklist executável", "Toda tarefa rastreia a um RF/RNF"], "fail": {"to": 2, "action": "tasks.md quebrado → re-decompor plan; se spec ambígua → reescrever spec.md"}},
    {"n": 4, "title": "Construção (TDD)", "icon": "🔨", "goal": "Implementar domain → application → infrastructure → api → mcp → tests, teste-primeiro.", "owner": "Builder (Worker)", "metric": "Coverage ≥85% + mutation pass + testes verde", "entrada": ["plan.md + tasks.md aprovados"], "saida": ["domain/ sem framework", "backend/modules/ + frontend/features/", "Migrations + testes"], "fail": {"to": 3, "action": "Implementação quebra gate → revisar plan/tasks; se gap de spec → voltar à Fase 2"}},
    {"n": 5, "title": "Gauntlet", "icon": "⚔️", "goal": "Builder + crítico cego compara o rewrite vs. legado, tela a tela. Só aprova quando o nosso ganha.", "owner": "Crítico cego", "metric": "crítico escolhe nosso cego + conformidade ADR 0004", "entrada": ["Implementação com testes verde", "Docs legados (a barra)"], "saida": ["qa-report.md com evidências", "Veredito: GANHOU", "Conformidade arquitetural verificada"], "fail": {"to": 4, "action": "REWORK: corrigir implementação, re-rodar TDD; se defeito de requisito → voltar à Fase 2"}},
    {"n": 6, "title": "Deploy", "icon": "🚀", "goal": "Deployar backend e frontend, com migrations + seeds idempotentes.", "owner": "Gerente", "metric": "health 200 + login E2E verde + 0 erro de console", "entrada": ["Código aprovado no gauntlet"], "saida": ["URL produção ativa", "DB migrado + seeds aplicados", "Health 200 + login E2E funcional"], "fail": {"to": 4, "action": "Deploy falha → corrigir config/Dockerfile; se bug de código → voltar à Fase 4"}},
]


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _e(s: str) -> str:
    """HTML-escape a string."""
    return escape(s) if s else ""


def _js_escape(s: str) -> str:
    """Escape a string for safe insertion into JS template literals (backtick strings)."""
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def _nav_item(icon_key: str, label: str, href: str = None, route: str = None,
              badge: str = None, active: bool = False) -> str:
    """Render a sidebar nav item."""
    ic = _ICONS.get(icon_key, "")
    badge_html = f'<span class="badge">{_e(badge)}</span>' if badge else ""
    cls = "nav-item" + (" active" if active else "")
    if href:
        return f'<a class="{cls}" href="{_e(href)}"><span class="ic">{ic}</span>{_e(label)} {badge_html}</a>'
    return f'<button class="{cls}" data-route="{_e(route)}"><span class="ic">{ic}</span>{_e(label)} {badge_html}</button>'


def _sidebar(active_page: str, project: dict, data: dict | None = None) -> str:
    """Render the shared sidebar. Flexible: adapts to project structure."""
    name = project.get("name", "PROJECT")
    subtitle = project.get("subtitle", "")
    n_modules = project.get("n_modules", "")
    n_adrs = project.get("n_adrs", "")

    # Determine label for modules section — "Módulos" if code exists, "Specs" if pre-implementation
    has_code = bool(data and data.get("modules"))
    modules_label = "Módulos" if has_code else "Specs"

    mod_badge = f' <span class="badge">{n_modules}</span>' if n_modules else ""
    adr_badge = f' <span class="badge">{n_adrs}</span>' if n_adrs else ""

    # Build nav items — index uses data-route for SPA, others use href
    def ni(icon, label, page, href=None, route=None, badge_html=""):
        ic = _ICONS.get(icon, "")
        cls = "nav-item" + (" active" if active_page == page else "")
        if href:
            return f'<a class="{cls}" href="{href}"><span class="ic">{ic}</span>{_e(label)}{badge_html}</a>'
        return f'<a class="{cls}" href="{href or "#"}"><span class="ic">{ic}</span>{_e(label)}{badge_html}</a>'

    # For index page, overview/taxonomy/workflow/adrs/metrics are data-route buttons
    if active_page == "index":
        ov = f'<button class="nav-item" data-route="overview"><span class="ic">{_ICONS["overview"]}</span>Visão geral</button>'
        tx = f'<button class="nav-item" data-route="taxonomy"><span class="ic">{_ICONS["taxonomy"]}</span>Taxonomia</button>'
        wf = f'<button class="nav-item" data-route="workflow"><span class="ic">{_ICONS["workflow"]}</span>Workflow</button>'
        ad = f'<button class="nav-item" data-route="adrs"><span class="ic">{_ICONS["adrs"]}</span>ADRs{adr_badge}</button>'
        mt = f'<button class="nav-item" data-route="metrics"><span class="ic">{_ICONS["metrics"]}</span>Métricas</button>'
        # Artifacts route (skills, scripts, journeys, prototype) — only if present
        art_btn = ""
        if data and (data.get("skills") or data.get("scripts") or data.get("journeys") or data.get("prototype")):
            art_btn = f'<button class="nav-item" data-route="artifacts"><span class="ic">{_ICONS["artifacts"]}</span>Artefatos</button>'
    else:
        ov = ni("overview", "Visão geral", "", href="index.html#overview")
        tx = ni("taxonomy", "Taxonomia", "", href="index.html#taxonomy")
        wf = ni("workflow", "Workflow", "", href="index.html#workflow")
        ad = ni("adrs", "ADRs", "", href="index.html#adrs", badge_html=adr_badge)
        mt = ni("metrics", "Métricas", "", href="index.html#metrics")
        art_btn = ""

    rm = ni("roadmap", "Roadmap", "roadmap", href="roadmap.html")
    md = ni("modules", modules_label, "modules", href="modules.html", badge_html=mod_badge)
    tr = ni("traceability", "Rastreabilidade", "traceability", href="traceability.html")

    return f"""\
<aside class="sidebar">
  <div class="brand">
    <div class="logo"><span class="mark">N</span><span class="name">{_e(name)}</span></div>
    <div class="sub">{_e(subtitle)}</div>
  </div>
  <div class="nav-group">
    <div class="label">Visão geral</div>
    {ov}
    {tx}
  </div>
  <div class="nav-group">
    <div class="label">Produto</div>
    {rm}
    {md}
    {tr}
  </div>
  <div class="nav-group">
    <div class="label">Engenharia</div>
    {wf}
    {ad}
    {art_btn}
  </div>
  <div class="nav-group">
    <div class="label">Métricas</div>
    {mt}
  </div>
</aside>"""


def _theme_toggle() -> str:
    return '<button class="theme-toggle" id="themeToggle" aria-label="Tema"></button>'


def _page(title: str, body: str, active_page: str, project: dict,
          extra_head: str = "", extra_css: str = "", script: str = "",
          data: dict | None = None) -> str:
    """Render a full HTML page."""
    lang = project.get("lang", "pt-BR")
    sidebar = _sidebar(active_page, project, data)
    css_link = '<link rel="stylesheet" href="styles.css" />'
    inline_css = f"\n<style>\n{extra_css}\n</style>" if extra_css else ""
    script_html = f"\n{script}" if script else ""

    return f"""<!doctype html>
<html lang="{_e(lang)}" data-theme="light">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{_e(title)}</title>
{_FONT_LINK}
{css_link}{inline_css}
{extra_head}
</head>
<body>
{_theme_toggle()}
<div class="app">
  {sidebar}
  <main class="main"{' id="content"' if active_page in ("index", "traceability") else ""}>
{body}
  </main>
</div>
{_THEME_SCRIPT}{script_html}
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────
# index.html — SPA shell (overview, taxonomy, workflow, ADRs, metrics)
# ──────────────────────────────────────────────────────────────────────

_INDEX_CSS = """
/* index-specific (taxonomy) */
.term{padding:20px 0;border-bottom:1px solid var(--border)}
.term:last-child{border-bottom:none}
.term .term-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.term .term-name{font-size:18px;font-weight:700;letter-spacing:-.01em}
.term .term-id{font-family:var(--font-mono);font-size:12px;color:var(--faint);background:var(--surface-2);padding:2px 8px;border-radius:5px;border:1px solid var(--border)}
.term .term-def{color:var(--muted);font-size:14.5px;margin:0 0 10px;max-width:70ch}
.term .term-map{font-size:13px;color:var(--ink);background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin:0}
.term .term-map b{color:var(--accent)}
"""


def _render_index(data: dict, project: dict) -> str:
    overview = data.get("overview", {})
    taxonomy = data.get("taxonomy", {})
    workflow = data.get("workflow", {})
    # Ensure 7 workflow phases — use defaults if fewer than 7
    if len(workflow.get("phases", [])) < 7:
        workflow["phases"] = _DEFAULT_WORKFLOW_PHASES
    adrs = data.get("adrs", [])
    metrics = data.get("metrics", [])

    # ALWAYS use the 15 fixed taxonomy terms — this is a product glossary, not project data
    taxonomy = {
        "categories": _DEFAULT_TAXONOMY_CATEGORIES,
        "terms": _DEFAULT_TAXONOMY_TERMS,
        "lede": "Os termos que estruturam este projeto, definidos e mapeados ao uso real — agrupados por dimensão com a hierarquia visível. A mesma linguagem ubíqua aparece em specs, código, UI e testes.",
        "callout": "<b>Régua:</b> nomenclatura alinhada ao <b>Atlassian Agile Coach + Product Guide</b> (hier; hierarquia épico→feature→story, critérios de aceitação); clareza e design pela <b>régua Linear</b>.",
    }

    # ── Overview ──
    ov_eyebrow = overview.get("eyebrow", "Visão geral")
    ov_title = overview.get("title", project.get("name", "Project"))
    ov_lede = overview.get("lede", "")
    ov_cards = ""

    # "O que é" card — product description
    ov_description = overview.get("description", ov_lede)
    if ov_description:
        ov_cards += f'<div class="card"><p class="card-title">📦 O que é</p><p class="muted">{ov_description}</p></div>\n'

    for card in overview.get("cards", []):
        ov_cards += f'<div class="card"><p class="card-title">{card.get("title","")}</p><p class="muted">{card.get("content","")}</p></div>\n'

    # Architecture card from stack data
    stack = data.get("stack", {})
    if stack:
        kv_rows = ""
        for k, v in stack.items():
            kv_rows += f"<dt>{_e(k.capitalize())}</dt><dd>{v}</dd>"
        ov_cards += f'<div class="card"><p class="card-title">🏗️ Arquitetura</p><dl class="kv">{kv_rows}</dl></div>\n'

    # "Estado" card — deploy info
    if stack.get("deploy"):
        ov_cards += f'<div class="card"><p class="card-title">✅ Estado</p><p class="muted">Deploy: {stack.get("deploy")}</p></div>\n'

    # ── Taxonomy ──
    cats = taxonomy.get("categories", [])
    terms = taxonomy.get("terms", [])
    tax_html = ""
    for cat in cats:
        cat_terms = [t for t in terms if t.get("cat") == cat.get("key")]
        tax_html += f'<h2 style="margin-top:36px">{cat.get("icon","")} {cat.get("label","")} <span class="faint" style="font-size:13px;font-weight:400">— {cat.get("hint","")}</span></h2>'
        for t in cat_terms:
            tax_html += f"""<div class="term"><div class="term-head"><span class="term-name">{t.get("term","")}</span><span class="term-id">{t.get("id","")}</span></div><p class="term-def">{t.get("def","")}</p><p class="term-map">{t.get("map","")}</p><p class="faint" style="font-size:12px;margin:6px 0 0;font-style:italic">↳ {t.get("analogy","")}</p></div>"""
    tax_lede = taxonomy.get("lede", "")
    tax_callout = taxonomy.get("callout", "")

    # ── Workflow ──
    phases = workflow.get("phases", [])
    wf_lede = workflow.get("lede", "")
    wf_callout = workflow.get("callout", "")

    def chk(items):
        return "".join(
            f'<li style="font-size:13px;color:var(--muted);margin-bottom:4px;list-style:none;padding-left:22px;position:relative"><span style="position:absolute;left:0;top:0">☐</span>{_e(i)}</li>'
            for i in items
        )

    phases_html = ""
    for p in phases:
        phases_html += f"""<div class="card" style="margin-bottom:14px"><p class="card-title"><span style="font-size:18px">{p.get("icon","")}</span> Fase {p.get("n","")} — {p.get("title","")} <span class="pill muted" style="margin-left:auto">{p.get("owner","")}</span></p><p class="muted" style="font-size:14px;margin:0 0 14px">{p.get("goal","")}</p><div class="grid grid-2" style="margin-bottom:14px"><div><p class="faint" style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin:0 0 6px">Entrada (critérios)</p><ul style="margin:0;padding:0">{chk(p.get("entrada",[]))}</ul></div><div><p class="faint" style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin:0 0 6px">Saída (verificável)</p><ul style="margin:0;padding:0">{chk(p.get("saida",[]))}</ul></div></div><p style="font-size:13px;margin:0 0 10px"><span class="pill ok">Métrica</span> <span class="muted mono" style="font-size:12px">{p.get("metric","")}</span></p><div style="border-left:3px solid var(--amber);background:rgba(176,107,0,.06);padding:10px 14px;border-radius:0 8px 8px 0;font-size:13px"><span class="pill wip">Se gate vermelho</span> <span class="muted"> → volta à <b>Fase {p.get("fail",{}).get("to","")}</b>: {p.get("fail",{}).get("action","")}</span></div></div>"""

    # ── ADRs ──
    adr_rows = ""
    for a in adrs:
        adr_rows += f'<div class="card"><p class="card-title">ADR {a.get("n","")} <span class="pill ok">{a.get("status","")}</span></p><p class="muted" style="font-size:13px;margin:0">{a.get("title","")}</p></div>'
    n_adrs = len(adrs)

    # ── Metrics ──
    metric_rows = ""
    for k, v in metrics:
        metric_rows += f"<dt>{_e(k)}</dt><dd><strong>{_e(v)}</strong></dd>"

    # ── SPA script ──
    # ── Artifacts (skills, scripts, journeys, prototype) ──
    skills = data.get("skills", [])
    scripts = data.get("scripts", [])
    journeys = data.get("journeys", [])
    prototype = data.get("prototype", None)
    has_artifacts = bool(skills or scripts or journeys or prototype)

    # Serialize data for client-side rendering
    tax_json = json.dumps(terms, ensure_ascii=False)
    adr_json = json.dumps(adrs, ensure_ascii=False)
    metrics_json = json.dumps(metrics, ensure_ascii=False)
    wf_json = json.dumps(phases, ensure_ascii=False)
    cats_json = json.dumps(cats, ensure_ascii=False)
    skills_json = json.dumps(skills, ensure_ascii=False)
    scripts_json = json.dumps(scripts, ensure_ascii=False)
    journeys_json = json.dumps(journeys, ensure_ascii=False)
    prototype_json = json.dumps(prototype, ensure_ascii=False)

    # Build routes dict — conditionally include artifacts
    routes_dict = "overview:renderOverview,taxonomy:renderTaxonomy,workflow:renderWorkflow,adrs:renderAdrs,metrics:renderMetrics"
    if has_artifacts:
        routes_dict += ",artifacts:renderArtifacts"

    script = f"""<script>
const TAXONOMY = {tax_json};
const ADRS = {adr_json};
const METRICS = {metrics_json};
const PHASES = {wf_json};
const CATS = {cats_json};
const SKILLS = {skills_json};
const SCRIPTS = {scripts_json};
const JOURNEYS = {journeys_json};
const PROTOTYPE = {prototype_json};
const routes = {{{routes_dict}}};
const el = document.getElementById("content");
function go(route){{
  const fn = routes[route] || renderOverview;
  el.innerHTML = "";
  fn(el);
  document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active", b.dataset.route===route));
  history.replaceState(null,"",`#${{route}}`);
  window.scrollTo(0,0);
}}
document.querySelectorAll(".nav-item[data-route]").forEach(b=>b.addEventListener("click",()=>go(b.dataset.route)));
function renderOverview(c){{c.innerHTML=`
  <p class="eyebrow">{_js_escape(_e(ov_eyebrow))}</p>
  <h1>{_js_escape(_e(ov_title))}</h1>
  <p class="lede">{_js_escape(ov_lede)}</p>
  {_js_escape(ov_cards)}
`;}}
function renderTaxonomy(c){{
  let html="";
  for(const cat of CATS){{const terms=TAXONOMY.filter(t=>t.cat===cat.key);html+=`<h2 style="margin-top:36px">${{cat.icon||""}} ${{cat.label||""}} <span class="faint" style="font-size:13px;font-weight:400">— ${{cat.hint||""}}</span></h2>`;for(const t of terms){{html+=`<div class="term"><div class="term-head"><span class="term-name">${{t.term||""}}</span><span class="term-id">${{t.id||""}}</span></div><p class="term-def">${{t.def||""}}</p><p class="term-map">${{t.map||""}}</p><p class="faint" style="font-size:12px;margin:6px 0 0;font-style:italic">↳ ${{t.analogy||""}}</p></div>`;}}}}
  c.innerHTML=`<p class="eyebrow">Nomenclatura</p><h1>Taxonomia de produto</h1><p class="lede">{_js_escape(tax_lede)}</p><div class="callout">{_js_escape(tax_callout)}</div>${{html}}`;
}}
function renderWorkflow(c){{
  const chk=(items)=>items.map(i=>`<li style="font-size:13px;color:var(--muted);margin-bottom:4px;list-style:none;padding-left:22px;position:relative"><span style="position:absolute;left:0;top:0">☐</span>${{i}}</li>`).join("");
  let phases=PHASES.map(p=>`<div class="card" style="margin-bottom:14px"><p class="card-title"><span style="font-size:18px">${{p.icon||""}}</span> Fase ${{p.n}} — ${{p.title||""}} <span class="pill muted" style="margin-left:auto">${{p.owner||""}}</span></p><p class="muted" style="font-size:14px;margin:0 0 14px">${{p.goal||""}}</p><div class="grid grid-2" style="margin-bottom:14px"><div><p class="faint" style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin:0 0 6px">Entrada (critérios)</p><ul style="margin:0;padding:0">${{chk(p.entrada||[])}}</ul></div><div><p class="faint" style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin:0 0 6px">Saída (verificável)</p><ul style="margin:0;padding:0">${{chk(p.saida||[])}}</ul></div></div><p style="font-size:13px;margin:0 0 10px"><span class="pill ok">Métrica</span> <span class="muted mono" style="font-size:12px">${{p.metric||""}}</span></p><div style="border-left:3px solid var(--amber);background:rgba(176,107,0,.06);padding:10px 14px;border-radius:0 8px 8px 0;font-size:13px"><span class="pill wip">Se gate vermelho</span> <span class="muted"> → volta à <b>Fase ${{p.fail.to}}</b>: ${{p.fail.action||""}}</span></div></div>`).join("");
  c.innerHTML=`<p class="eyebrow">Engenharia</p><h1>Workflow reproduzível</h1><p class="lede">{_js_escape(wf_lede)}</p><div class="callout">{_js_escape(wf_callout)}</div>${{phases}}`;
}}
function renderAdrs(c){{
  let rows=ADRS.map(a=>{{let desc=a.description?`<p class="muted" style="font-size:12.5px;margin:6px 0 0;line-height:1.5">${{a.description}}</p>`:"";let ctx=a.context?`<p class="faint" style="font-size:11.5px;margin:4px 0 0;font-style:italic">Contexto: ${{a.context}}</p>`:"";return `<div class="card"><p class="card-title">ADR ${{a.n}} <span class="pill ok">${{a.status||""}}</span></p><p class="muted" style="font-size:13px;margin:0">${{a.title||""}}</p>${{desc}}${{ctx}}</div>`;}}).join("");
  c.innerHTML=`<p class="eyebrow">Engenharia</p><h1>Architecture Decision Records</h1><p class="lede">Decisões imutáveis e datadas. Nunca reescritas — substituídas por um novo ADR que referencia o anterior.</p><div class="grid grid-2">${{rows}}</div>`;
}}
function renderMetrics(c){{
  let rows=METRICS.map(([k,v])=>`<dt>${{k}}</dt><dd><strong>${{v}}</strong></dd>`).join("");
  c.innerHTML=`<p class="eyebrow">Métricas</p><h1>Métricas do projeto</h1><p class="lede">Estado quantificado do projeto.</p><div class="card"><dl class="kv">${{rows}}</dl></div>`;
}}
function renderArtifacts(c){{
  let html="<p class='eyebrow'>Engenharia</p><h1>Artefatos</h1><p class='lede'>Skills, scripts, jornadas e protótipo — artefatos de engenharia e produto do projeto.</p>";
  if(SKILLS.length){{html+=`<h2>Skills (${{SKILLS.length}})</h2><div class="grid grid-2">`+SKILLS.map(s=>`<div class="card"><p class="card-title">${{s.name||""}}</p><p class="muted" style="font-size:13px;margin:0">${{s.description||""}}</p>${{s.path?`<p class="faint" style="font-size:11px;margin:6px 0 0"><a href="${{s.path}}">${{s.path}}</a></p>`:""}}</div>`).join("")+"</div>";}}
  if(SCRIPTS.length){{html+=`<h2>Scripts (${{SCRIPTS.length}})</h2><div class="grid grid-2">`+SCRIPTS.map(s=>`<div class="card"><p class="card-title"><code>${{s.name||""}}</code></p><p class="muted" style="font-size:13px;margin:0">${{s.description||""}}</p>${{s.type?`<span class="pill muted" style="margin-top:6px">${{s.type}}</span>`:""}}</div>`).join("")+"</div>";}}
  if(JOURNEYS.length){{html+=`<h2>Jornadas (${{JOURNEYS.length}})</h2>`+JOURNEYS.map(j=>`<div class="card"><p class="card-title">${{j.name||j.id||""}}</p><p class="muted" style="font-size:13px;margin:0">${{j.description||""}}</p>${{j.steps?`<span class="pill ok" style="margin-top:6px">${{j.steps}} passos</span>`:""}}</div>`).join("");}}
  if(PROTOTYPE){{html+=`<h2>Protótipo</h2><div class="card"><p class="card-title">${{PROTOTYPE.name||"Protótipo"}}</p><p class="muted" style="font-size:13px;margin:0">${{PROTOTYPE.description||""}}</p>${{PROTOTYPE.path?`<p style="margin:8px 0 0"><a href="${{PROTOTYPE.path}}">Abrir protótipo →</a></p>`:""}}</div>`;}}
  c.innerHTML=html;
}}
go(location.hash.slice(1)||"overview");
</script>"""

    body = ""  # SPA — content rendered by JS
    return _page(
        f'{project.get("name","")} — Produto',
        body,
        "index",
        project,
        extra_css=_INDEX_CSS,
        script=script,
        data=data,
    )


# ──────────────────────────────────────────────────────────────────────
# modules.html — modules as epics
# ──────────────────────────────────────────────────────────────────────

_MODULES_CSS = """
/* ── Summary strip ── */
.summary{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:24px}
@media(max-width:860px){.summary{grid-template-columns:repeat(4,1fr)}}
@media(max-width:520px){.summary{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px;box-shadow:var(--shadow)}
.stat .v{font-size:22px;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.stat .k{font-size:10.5px;font-weight:600;color:var(--faint);text-transform:uppercase;letter-spacing:.06em;margin-top:3px}

/* ── Jump bar ── */
.jumpbar{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px}
.jumpbar a{font-size:12px;font-weight:600;font-family:var(--font-mono);background:var(--surface);border:1px solid var(--border);border-radius:7px;padding:5px 10px;color:var(--muted)}
.jumpbar a:hover{border-color:var(--accent);color:var(--accent);text-decoration:none}

/* ── Module section (always open, densified) ── */
.mod{background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);margin-bottom:12px;padding:18px 22px 20px}
.mod-head{display:flex;align-items:flex-start;gap:12px;margin-bottom:10px}
.mod-tag{flex-shrink:0;width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;color:#fff;letter-spacing:-.02em}
.mod-title{font-size:16px;font-weight:700;letter-spacing:-.01em;margin:0 0 2px}
.mod-sub{font-size:12.5px;color:var(--muted);margin:0}
.mod-sub .sep{color:var(--border-strong);margin:0 5px}
.mod-status{margin-left:auto;flex-shrink:0;font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;align-self:flex-start}
.mod-status.ok{background:rgba(26,122,76,.12);color:var(--green)}
.mod-status.tv{background:var(--surface-2);color:var(--faint)}

.vision{font-size:13.5px;color:var(--muted);margin:0 0 12px;max-width:78ch;line-height:1.55}

/* dependency line */
.deps{font-size:12.5px;margin:0 0 12px;padding:7px 11px;background:var(--surface-2);border:1px solid var(--border);border-radius:7px}
.deps b{color:var(--ink);font-weight:650}

/* two-col body: left = features, right = criteria+tools+links */
.mod-body{display:grid;grid-template-columns:1.55fr 1fr;gap:20px}
@media(max-width:760px){.mod-body{grid-template-columns:1fr}}
.slabel{font-size:10.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin:0 0 7px}

/* feature list (compact rows) */
.features{display:flex;flex-direction:column;gap:0}
.feat{display:flex;align-items:baseline;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);font-size:13px;line-height:1.4}
.feat:last-child{border-bottom:none}
.feat-name{font-weight:650;color:var(--ink);flex-shrink:0}
.feat-desc{color:var(--muted);flex:1;min-width:0}
.feat-meta{font-family:var(--font-mono);font-size:10.5px;color:var(--faint);flex-shrink:0;white-space:nowrap}

/* acceptance criteria */
.ac{display:flex;flex-direction:column;gap:5px;margin-bottom:14px}
.ac-item{display:flex;align-items:flex-start;gap:7px;font-size:12.5px;color:var(--muted);line-height:1.4}
.ac-check{color:var(--green);font-weight:700;flex-shrink:0;font-size:12px;line-height:1.5}

/* metric mini-grid */
.mgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:14px}
@media(max-width:520px){.mgrid{grid-template-columns:repeat(3,1fr)}}
.mcell{background:var(--surface-2);border:1px solid var(--border);border-radius:7px;padding:8px 10px}
.mcell .mv{font-size:17px;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.mcell .mk{font-size:9.5px;font-weight:600;color:var(--faint);text-transform:uppercase;letter-spacing:.05em;margin-top:2px}
.tv-note{font-size:12.5px;color:var(--muted);padding:9px 11px;background:var(--surface-2);border:1px solid var(--border);border-radius:7px;margin-bottom:14px}

/* MCP tools chips */
.chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px}
.chip{font-family:var(--font-mono);font-size:10.5px;background:var(--surface-2);border:1px solid var(--border);border-radius:5px;padding:2px 7px;color:var(--accent)}

/* links */
.links{display:flex;flex-wrap:wrap;gap:8px}
.links a{font-size:11.5px;font-weight:600;font-family:var(--font-mono);background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:4px 9px;color:var(--muted)}
.links a:hover{border-color:var(--accent);color:var(--accent);text-decoration:none}

@media(max-width:720px){.main{padding:28px 18px 80px}.sidebar{display:none}}
"""


def _render_modules(data: dict, project: dict) -> str:
    modules = data.get("modules", [])
    specs = data.get("specs", [])

    # If no code modules, use specs as epics (pre-implementation)
    use_specs = not modules and bool(specs)
    epics = modules if modules else specs

    # Summary strip — adapt labels to project state
    has_code = bool(modules)
    totals = {
        "count": len(epics),
        "rf": sum(m.get("rf", len(m.get("rfs", []))) for m in epics),
        "endpoints": sum(m.get("endpoints", 0) for m in epics),
        "tools": sum(m.get("tools", 0) for m in epics),
        "telas": sum(m.get("telas", 0) for m in epics),
        "testes": sum(m.get("testes", 0) for m in epics),
    }
    count_label = "Módulos" if has_code else "Specs"
    summary_items = [
        (count_label, totals["count"]),
        ("RFs", totals["rf"]),
    ]
    if has_code:
        summary_items += [
            ("Endpoints", totals["endpoints"]),
            ("MCP tools", totals["tools"]),
            ("Telas", totals["telas"]),
            ("Testes", totals["testes"]),
            ("Gauntlet", project.get("gauntlet", "7/7")),
        ]
    else:
        adrs_count = len(data.get("adrs", []))
        skills_count = len(data.get("skills", []))
        summary_items += [
            ("ADRs", adrs_count),
            ("Skills", skills_count),
            ("Jornadas", len(data.get("journeys", []))),
            ("Scripts", len(data.get("scripts", []))),
            ("Estado", "pré-impl"),
        ]

    summary_html = '<div class="summary">'
    for k, v in summary_items:
        summary_html += f'<div class="stat"><div class="v">{v}</div><div class="k">{_e(k)}</div></div>'
    summary_html += "</div>"

    # Jump bar
    jumpbar = '<div class="jumpbar">'
    for m in epics:
        jumpbar += f'<a href="#{m.get("id","")}">{m.get("id","")}</a>'
    jumpbar += "</div>"

    # Epic sections
    mods_html = ""
    for m in epics:
        mid = m.get("id", "")
        mname = m.get("name", "")
        color = m.get("color", "#5b5bd6")
        transversal = m.get("transversal", False)
        vision = m.get("vision", m.get("description", ""))
        if not vision:
            # Use spec name as unique vision — each spec has its own
            vision = mname or mid
        deps = m.get("deps", "")
        rf = m.get("rf", len(m.get("rfs", [])))
        endpoints = m.get("endpoints", 0)
        tools = m.get("tools", 0)
        telas = m.get("telas", 0)
        testes = m.get("testes", 0)
        spec = m.get("spec", m.get("specNum", ""))
        spec_dir = m.get("specDir", m.get("specDir", ""))
        backend = m.get("backend", "")
        frontend = m.get("frontend", "")
        status_val = m.get("status", "")

        # Status — gauntlet for code modules, spec status for pre-implementation
        if transversal:
            status = '<span class="mod-status tv">transversal</span>'
        elif has_code:
            status = '<span class="mod-status ok">✓ gauntlet</span>'
        elif status_val:
            status_cls = "ok" if status_val.lower() in ("aprovada", "accepted", "done") else "tv"
            status = f'<span class="mod-status {status_cls}">{_e(status_val)}</span>'
        else:
            status = ""

        # Features — if empty, group RFs into 3-5 thematic features with human names
        features = m.get("features", [])
        if not features:
            rfs = m.get("rfs", [])
            if rfs:
                # Check if generate.py provided feature_themes
                feature_themes = m.get("feature_themes", [])
                # Group RFs into thematic chunks of ~3-4 each
                rf_count = len(rfs)
                group_size = max(2, (rf_count + 2) // 4)  # ~4 groups
                features = []
                for gi in range(0, rf_count, group_size):
                    chunk = rfs[gi:gi + group_size]
                    rf_ids = []
                    rf_descs = []
                    for rf_item in chunk:
                        if isinstance(rf_item, dict):
                            rf_ids.append(rf_item.get("id", ""))
                            rf_descs.append(rf_item.get("d", rf_item.get("text", "")))
                        elif isinstance(rf_item, str):
                            rf_descs.append(rf_item)
                    idx = gi // group_size

                    # Determine feature name
                    if idx < len(feature_themes):
                        feat_name = feature_themes[idx]
                    elif rf_descs:
                        # Derive from first 3-4 words of first RF (strip EARS prefixes)
                        first_words = rf_descs[0]
                        for prefix in ("QUANDO ", "O SISTEMA DEVE ", "THE SYSTEM SHALL ", "IF ", "WHEN "):
                            first_words = first_words.replace(prefix, "", 1) if first_words.startswith(prefix) else first_words
                        words = first_words.split()[:4]
                        feat_name = " ".join(words).capitalize()
                    else:
                        feat_name = f"RFs {rf_ids[0] if rf_ids else ''}"

                    rf_range = f"{rf_ids[0]}-{rf_ids[-1]}" if len(rf_ids) > 1 else (rf_ids[0] if rf_ids else "")
                    features.append({
                        "n": feat_name,
                        "d": f"{len(chunk)} RFs ({rf_range}): " + "; ".join(d[:80] for d in rf_descs[:2]) + ("..." if len(rf_descs) > 2 else ""),
                    })
        feats_html = ""
        for f in features:
            if isinstance(f, dict):
                ep = f.get("ep", 0)
                t = f.get("t", 0)
                meta = f"{ep} ep · {t} tela{'s' if t != 1 else ''}" if (ep or t) else ""
                feats_html += f'<div class="feat"><span class="feat-name">{_e(f.get("n",""))}</span><span class="feat-desc">{_e(f.get("d",""))}</span><span class="feat-meta">{_e(meta)}</span></div>'
            elif isinstance(f, str):
                feats_html += f'<div class="feat"><span class="feat-name">{_e(f)}</span></div>'

        # Acceptance criteria — if empty, derive from RFs preserving original Portuguese
        ac_items = m.get("ac", [])
        if not ac_items and not has_code:
            rfs = m.get("rfs", [])
            for rf_item in rfs[:5]:  # max 5 ACs
                if isinstance(rf_item, dict):
                    rf_text = rf_item.get("d", rf_item.get("text", ""))
                elif isinstance(rf_item, str):
                    rf_text = rf_item
                else:
                    continue
                if not rf_text:
                    continue
                # Extract text after EARS markers — preserve original Portuguese
                ac_text = rf_text
                for marker in ("O SISTEMA DEVE ", "THE SYSTEM SHALL ", "DEVE ", "SHALL "):
                    mu = ac_text.upper()
                    if marker in mu:
                        idx = mu.find(marker)
                        ac_text = ac_text[idx + len(marker):]
                        break
                ac_text = ac_text.strip()
                # Capitalize first letter
                if ac_text:
                    ac_text = ac_text[0].upper() + ac_text[1:]
                # Truncate if too long
                if len(ac_text) > 100:
                    ac_text = ac_text[:97] + "..."
                ac_items.append(f"✓ {ac_text}" if ac_text else f"✓ {rf_text[:80]}")
            # Add status as last AC if still empty
            if not ac_items and status_val:
                ac_items = [f"Spec {status_val}"]
        ac_html = ""
        for c in ac_items:
            ac_html += f'<div class="ac-item"><span class="ac-check">✓</span><span>{c}</span></div>'

        # Metrics grid or transversal note
        if transversal:
            metrics_html = f'<div class="tv-note">Módulo transversal — <b>{rf} RFs de UI/UX</b>, sem endpoints, MCP tools ou telas próprios.</div>'
        elif has_code:
            metrics_html = f"""<div class="mgrid">
              <div class="mcell"><div class="mv">{rf}</div><div class="mk">RFs</div></div>
              <div class="mcell"><div class="mv">{endpoints}</div><div class="mk">Endpoints</div></div>
              <div class="mcell"><div class="mv">{tools}</div><div class="mk">MCP tools</div></div>
              <div class="mcell"><div class="mv">{telas}</div><div class="mk">Telas</div></div>
              <div class="mcell"><div class="mv">{testes}</div><div class="mk">Testes</div></div>
            </div>"""
        else:
            # Pre-implementation: show spec artifacts count
            artifacts = m.get("artifacts", [])
            art_count = len(artifacts) if artifacts else 0
            metrics_html = f'<div class="tv-note"><b>{rf} RFs</b> · {art_count} artefatos de spec · pré-implementação</div>'

        # MCP tools chips
        tool_list = m.get("toolList", [])
        tools_html = ""
        if tool_list:
            chips = "".join(f'<span class="chip">{_e(t)}</span>' for t in tool_list)
            tools_html = f'<p class="slabel">MCP tools ({tools})</p><div class="chips">{chips}</div>'

        # Links — adapt to project state
        links_parts = []
        if spec_dir:
            links_parts.append(f'<a href="../../specs/{spec_dir}/spec.md" target="_blank">📄 spec.md</a>')
            # Spec artifacts (plan, tasks, qa-report, retro, ux-design)
            for art in m.get("artifacts", []):
                art_name = art if isinstance(art, str) else art.get("name", "")
                art_path = art if isinstance(art, str) else art.get("path", f"../../specs/{spec_dir}/{art_name}")
                links_parts.append(f'<a href="{_e(art_path)}" target="_blank">📋 {_e(art_name)}</a>')
        if backend:
            links_parts.append(f'<a href="../../backend/app/modules/{backend}/" target="_blank">⚙️ backend</a>')
        elif not has_code and not use_specs:
            links_parts.append('<a href="../../docs/design-system/" target="_blank">🎨 design-system</a>')
        if frontend:
            links_parts.append(f'<a href="../../frontend/src/features/{frontend}/" target="_blank">🖥️ frontend</a>')
        links_html = " ".join(links_parts)

        # Sub-title line
        if has_code:
            sub_line = f'Spec <code>{spec}</code><span class="sep">·</span>{rf} RFs<span class="sep">·</span>{endpoints} endpoints<span class="sep">·</span>{tools} MCP tools<span class="sep">·</span>{telas} telas<span class="sep">·</span>{testes} testes'
        else:
            sub_line = f'Spec <code>{spec}</code><span class="sep">·</span>{rf} RFs'
            if status_val:
                sub_line += f'<span class="sep">·</span>{_e(status_val)}'

        mods_html += f"""
  <div class="mod" id="{mid}">
    <div class="mod-head">
      <div class="mod-tag" style="background:{color}">{mid}</div>
      <div>
        <p class="mod-title">{mid} — {_e(mname)}</p>
        <p class="mod-sub">{sub_line}</p>
      </div>
      {status}
    </div>
    <p class="vision">{vision}</p>
    {f'<p class="deps">{deps}</p>' if deps else ''}
    <div class="mod-body">
      <div>
        <p class="slabel">Features ({len(features)})</p>
        <div class="features">{feats_html}</div>
      </div>
      <div>
        <p class="slabel">Critérios de aceitação</p>
        <div class="ac">{ac_html}</div>
        {metrics_html}
        {tools_html}
        <p class="slabel">Links</p>
        <div class="links">{links_html}</div>
      </div>
    </div>
  </div>"""

    page_title = f'{project.get("name","")} — {"Módulos (Épicos)" if has_code else "Specs (Épicos)"}'
    lede_text = (
        "Cada módulo é um <strong>Bounded Context</strong> (DDD) e um <strong>épico de produto</strong>, decomposto em features com critérios de aceitação e dependências explícitas."
        if has_code
        else "Cada spec é um <strong>épico de produto</strong>, decomposto em features com critérios de aceitação. Projeto em pré-implementação — sem código de produção ainda."
    )

    body = f"""\
    <p class="eyebrow">Produto</p>
    <h1>{"Módulos (Épicos)" if has_code else "Specs (Épicos)"}</h1>
    <p class="lede">{lede_text}</p>
    {summary_html}
    <div class="callout"><b>Barra:</b> estrutura épico → feature → story (Atlassian); densidade e clareza (régua Linear). Conteúdo sempre-aberto — sem accordions.</div>
    {jumpbar}
    {mods_html}"""

    return _page(
        page_title,
        body,
        "modules",
        project,
        extra_css=_MODULES_CSS,
        data=data,
    )


# ──────────────────────────────────────────────────────────────────────
# traceability.html — requirements with forward/backward chain
# ──────────────────────────────────────────────────────────────────────

_TRACE_CSS = """
/* traceability supplementary */
.grid-3{grid-template-columns:repeat(3,1fr)}
@media(max-width:900px){.grid-3{grid-template-columns:1fr}}
.pill.rf{background:rgba(91,91,214,.12);color:var(--accent)}
.pill.rnf{background:rgba(43,108,176,.12);color:var(--blue)}

/* ── Traceability-specific ── */
.stat-tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px;text-align:center}
.stat-tile .num{font-size:28px;font-weight:800;letter-spacing:-.02em;color:var(--ink)}
.stat-tile .lbl{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-top:2px}

.req-row{display:grid;grid-template-columns:62px 1fr 120px;gap:8px 12px;align-items:start;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px}
.req-row:last-child{border-bottom:none}
.req-row .req-id{font-family:var(--font-mono);font-size:11.5px;font-weight:600;color:var(--accent);white-space:nowrap}
.req-row.rnf .req-id{color:var(--blue)}
.req-row .req-desc{color:var(--ink);line-height:1.45}
.req-row .req-src{font-size:10.5px;color:var(--faint);font-family:var(--font-mono);text-align:right;white-space:normal}
.req-row .req-src a{color:var(--faint);text-decoration:none;border-bottom:1px dotted var(--border-strong)}
.req-row .req-src a:hover{color:var(--accent);border-bottom-color:var(--accent)}

/* status pill before ID */
.st-pill{display:inline-block;font-size:9px;font-weight:700;padding:1px 5px;border-radius:4px;letter-spacing:.02em;vertical-align:middle}
.st-pill.ok{background:rgba(26,122,76,.15);color:var(--green)}
.st-pill.wip{background:rgba(176,107,0,.15);color:var(--amber)}
.st-pill.na{background:var(--surface-2);color:var(--faint)}

/* forward chain row */
.fwd-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:3px 0 6px 74px;border-bottom:1px solid var(--border);font-size:11px}
.fwd-row:last-child{border-bottom:none}
.fwd-label{color:var(--faint);font-weight:600;text-transform:uppercase;letter-spacing:.05em;font-size:9.5px}
.fwd-link{font-family:var(--font-mono);font-size:10.5px;padding:2px 7px;border-radius:5px;background:var(--surface-2);border:1px solid var(--border);color:var(--muted);text-decoration:none;white-space:nowrap}
.fwd-link:hover{border-color:var(--accent);color:var(--accent);text-decoration:none}
.fwd-link.tela{color:var(--blue)}
.fwd-link.ep{color:var(--accent)}
.fwd-link.test{color:var(--green)}
.fwd-arrow{color:var(--faint);font-size:10px}
.fwd-ac{font-size:11px;color:var(--muted);font-style:italic;margin-left:8px}

.module-section{margin-bottom:36px}
.module-header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px}
.module-header .m-id{font-family:var(--font-mono);font-size:13px;font-weight:700;color:var(--accent);background:var(--accent-soft);padding:4px 10px;border-radius:7px}
.module-header .m-name{font-size:18px;font-weight:700;letter-spacing:-.01em}
.module-header .m-links{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.module-header .m-links a{font-size:12px;font-weight:500;padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:var(--surface)}
.module-header .m-links a:hover{border-color:var(--accent);text-decoration:none}

.source-list{font-size:12px;color:var(--muted);margin:0 0 16px;line-height:1.7}
.source-list .src-tag{font-family:var(--font-mono);font-size:11px;background:var(--surface-2);border:1px solid var(--border);padding:1px 6px;border-radius:4px;margin-right:6px;display:inline-block;margin-bottom:2px;color:var(--muted);text-decoration:none}
.source-list .src-tag:hover{border-color:var(--accent);color:var(--accent);text-decoration:none}

.req-table{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;box-shadow:var(--shadow)}
.req-table .rt-head{display:grid;grid-template-columns:72px 1fr 130px;gap:10px 14px;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);padding-bottom:8px;border-bottom:1px solid var(--border);margin-bottom:4px}
.req-table .rt-head .rt-src{text-align:right}

.section-label{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin:18px 0 6px}

.filter-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.filter-chip{font-size:12px;font-weight:600;padding:5px 12px;border-radius:999px;border:1px solid var(--border);background:var(--surface);cursor:pointer;color:var(--muted);font-family:inherit}
.filter-chip:hover{border-color:var(--accent);color:var(--ink)}
.filter-chip.active{background:var(--accent);color:#fff;border-color:var(--accent)}

.search-box{width:100%;padding:10px 14px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--ink);font-size:14px;font-family:inherit;margin-bottom:16px}
.search-box:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
"""


def _render_traceability(data: dict, project: dict) -> str:
    tr_modules = data.get("traceability", {}).get("modules", [])

    # Serialize data for client-side rendering (same pattern as reference)
    tr_json = json.dumps(tr_modules, ensure_ascii=False)

    body = ""  # rendered by JS

    script = f"""<script>
const MODULES = {tr_json};
const el = document.getElementById("content");
let currentFilter = "all";
let searchTerm = "";

function countAll(){{
  let rf=0, rnf=0, src=0;
  MODULES.forEach(m=>{{rf+=m.rfs.length; rnf+=m.rnfs.length; src+=m.sources.length;}});
  return {{rf,rnf,src,modules:MODULES.length}};
}}

function renderOverview(){{
  const c = countAll();
  // Calculate actual traceability — RFs/RNFs that have a source citation
  let tracedCount = 0;
  MODULES.forEach(m=>{{
    tracedCount += m.rfs.filter(r=>r.s).length;
    tracedCount += m.rnfs.filter(r=>r.s).length;
  }});
  const totalCount = c.rf + c.rnf;
  const pct = totalCount > 0 ? Math.round(tracedCount / totalCount * 100) : 0;
  const tiles = `
    <div class="grid grid-3" style="margin-bottom:24px">
      <div class="stat-tile"><div class="num">${{c.modules}}</div><div class="lbl">Módulos</div></div>
      <div class="stat-tile"><div class="num">${{c.rf}}</div><div class="lbl">Requisitos funcionais</div></div>
      <div class="stat-tile"><div class="num">${{c.rnf}}</div><div class="lbl">Requisitos não-funcionais</div></div>
    </div>
    <div class="grid grid-3" style="margin-bottom:28px">
      <div class="stat-tile"><div class="num">${{c.src}}</div><div class="lbl">Fontes legadas (§9)</div></div>
      <div class="stat-tile"><div class="num">${{totalCount}}</div><div class="lbl">Requisitos totais</div></div>
      <div class="stat-tile"><div class="num">${{pct}}%</div><div class="lbl">Rastreiam ao legado</div></div>
    </div>`;
  const moduleSummary = MODULES.map(m=>`
    <div class="card" style="cursor:pointer" onclick="setFilter('${{m.id}}')">
      <p class="card-title"><span class="pill rf">${{m.id}}</span> ${{m.name||""}}</p>
      <p class="card-sub">${{m.rfs.length}} RF · ${{m.rnfs.length}} RNF · ${{m.sources.length}} fontes</p>
      <p class="muted" style="font-size:12px;margin:0">Spec <code>${{m.specNum||""}}</code> · <a href="${{m.specPath||""}}" onclick="event.stopPropagation()">${{(m.specPath||"").split('/').pop()}}</a></p>
    </div>`).join("");
  return `
    <p class="eyebrow">Rastreabilidade</p>
    <h1>Matriz de rastreabilidade</h1>
    <p class="lede">Necessidade de negócio (doc legado) → requisito (RF/RNF) → spec → módulo → endpoint/tela → teste. Cada requisito cita a fonte da qual foi extraído (§9 de cada spec).</p>
    <div class="callout"><b>Como ler:</b> cada RF e RNF tem ID, descrição, fonte legada (link clicável) e <b>cadeia forward</b> navegável: spec → tela → endpoint → teste.</div>
    ${{tiles}}
    <h2>Resumo por módulo</h2>
    <div class="grid grid-2">${{moduleSummary}}</div>`;
}}

function lookupFwd(m, rfNum){{
  if(!m.fwdMap) return null;
  for(const f of m.fwdMap){{ if(rfNum>=f.rf[0] && rfNum<=f.rf[1]) return f; }}
  return null;
}}
function lookupRnfFwd(m, rnfNum){{
  if(!m.rnfFwdMap) return null;
  for(const f of m.rnfFwdMap){{ if(rnfNum>=f.rf[0] && rnfNum<=f.rf[1]) return f; }}
  return null;
}}

function renderSrcLinks(s, m){{
  return s.replace(/([A-Za-z][-A-Za-z0-9]*\\d+)/g, (match) => {{
    const src = m.sources.find(x=>x.tag===match);
    if(src) return `<a href="../../${{src.path}}" title="${{src.desc||""}}">${{match}}</a>`;
    return match;
  }});
}}

function renderFwd(m, rId, isRnf){{
  const num = parseInt(rId.replace(/[^0-9]/g,""));
  const f = isRnf ? lookupRnfFwd(m, num) : lookupFwd(m, num);
  if(!f){{
    // No forward map — show at least spec → RF
    const parts = [`<a class="fwd-link" href="${{m.specPath||""}}">spec</a>`, `<span class="fwd-link">${{rId}}</span>`];
    const chain = parts.join(' <span class="fwd-arrow">→</span> ');
    return `<div class="fwd-row"><span class="fwd-label">cadeia</span> ${{chain}} <span class="fwd-ac">↳ sem implementação ainda</span></div>`;
  }}
  const parts = [`<a class="fwd-link" href="${{m.specPath||""}}">spec</a>`];
  if(f.tela) parts.push(`<a class="fwd-link tela" href="../../frontend/src/features/${{m.frontend||""}}/${{f.tela}}">${{f.tela}}</a>`);
  if(f.ep) parts.push(`<a class="fwd-link ep" href="../../backend/app/modules/${{m.backend||""}}/api/">${{f.ep}}</a>`);
  if(f.test) parts.push(`<a class="fwd-link test" href="${{m.backend?'../../backend/app/modules/'+m.backend+'/tests/':'../../frontend/src/'}}${{f.test}}">${{f.test}}</a>`);
  // If only spec in chain (no tela/ep/test), add placeholder
  if(parts.length === 1) parts.push(`<span class="fwd-link">pré-implementação</span>`);
  const chain = parts.join(' <span class="fwd-arrow">→</span> ');
  const ac = f.ac ? `<span class="fwd-ac">↳ ${{f.ac}}</span>` : "";
  return `<div class="fwd-row"><span class="fwd-label">cadeia</span> ${{chain}} ${{ac}}</div>`;
}}

function renderModule(m){{
  const sources = m.sources.map(s=>`<a class="src-tag" href="../../${{s.path}}" title="${{s.desc||""}}">${{s.tag}}</a>`).join("");
  const rfVerified = m.rfs.filter(r=>lookupFwd(m, parseInt(r.id.replace(/[^0-9]/g,"")))).length;
  const rnfVerified = m.rnfs.filter(r=>lookupRnfFwd(m, parseInt(r.id.replace(/[^0-9]/g,"")))).length;
  const rfRows = m.rfs.map(r=>{{const num=parseInt(r.id.replace(/[^0-9]/g,""));const f=lookupFwd(m,num);const st=f?'':'<span class="st-pill wip">◐</span>';return `<div class="req-row"><span class="req-id">${{st}}${{r.id}}</span><span class="req-desc">${{r.d||""}}</span><span class="req-src">${{renderSrcLinks(r.s||"",m)}}</span></div>${{renderFwd(m,r.id,false)}}`;}}).join("");
  const rnfRows = m.rnfs.map(r=>{{const num=parseInt(r.id.replace(/[^0-9]/g,""));const f=lookupRnfFwd(m,num);const st=f?'':'<span class="st-pill wip">◐</span>';return `<div class="req-row rnf"><span class="req-id">${{st}}${{r.id}}</span><span class="req-desc">${{r.d||""}}</span><span class="req-src">${{renderSrcLinks(r.s||"",m)}}</span></div>${{renderFwd(m,r.id,true)}}`;}}).join("");
  return `
    <div class="module-section" data-mid="${{m.id}}">
      <div class="module-header">
        <span class="m-id">${{m.id}}</span>
        <span class="m-name">${{m.name||""}}</span>
        <span class="m-links">
          <span class="st-pill ok">${{rfVerified}}/${{m.rfs.length}} RF ✓</span>
          <span class="st-pill ok">${{rnfVerified}}/${{m.rnfs.length}} RNF ✓</span>
          <a href="${{m.specPath||""}}">spec.md</a>
          <a href="${{m.modulePath||""}}">módulo</a>
        </span>
      </div>
      <div class="source-list"><strong>Fontes consultadas (§9):</strong> ${{sources}}</div>
      <div class="req-table">
        <div class="rt-head"><span>ID</span><span>Requisito funcional — cadeia: spec → tela → endpoint → teste</span><span class="rt-src">Fonte legada</span></div>
        ${{rfRows}}
      </div>
      <div class="req-table" style="margin-top:14px">
        <div class="rt-head"><span>ID</span><span>Requisito não-funcional — cadeia: spec → teste</span><span class="rt-src">Fonte legada</span></div>
        ${{rnfRows}}
      </div>
    </div>`;
}}

function renderFiltered(){{
  let html = `
    <p class="eyebrow">Rastreabilidade</p>
    <h1>Matriz de rastreabilidade</h1>
    <p class="lede">Necessidade de negócio (doc legado) → requisito (RF/RNF) → spec → módulo → endpoint/tela → teste.</p>
    <input class="search-box" id="searchBox" placeholder="Buscar por ID, descrição ou fonte..." value="${{searchTerm}}">
    <div class="filter-bar">
      <button class="filter-chip" data-filter="all">Todos</button>
      ${{MODULES.map(m=>`<button class="filter-chip" data-filter="${{m.id}}">${{m.id}}</button>`).join("")}}
    </div>`;
  let modules = currentFilter==="all" ? MODULES : MODULES.filter(m=>m.id===currentFilter);
  if(searchTerm){{
    const q = searchTerm.toLowerCase();
    modules = modules.map(m=>{{
      const rfs = m.rfs.filter(r=>r.id.toLowerCase().includes(q)||(r.d||"").toLowerCase().includes(q)||(r.s||"").toLowerCase().includes(q));
      const rnfs = m.rnfs.filter(r=>r.id.toLowerCase().includes(q)||(r.d||"").toLowerCase().includes(q)||(r.s||"").toLowerCase().includes(q));
      return {{...m, rfs, rnfs}};
    }}).filter(m=>m.rfs.length>0||m.rnfs.length>0);
  }}
  if(modules.length===0){{html += `<div class="callout">Nenhum requisito encontrado para "${{searchTerm}}".</div>`;}}
  else{{modules.forEach(m=>{{ html += renderModule(m); }});}}
  return html;
}}

function render(){{
  if(currentFilter==="all" && !searchTerm){{el.innerHTML = renderOverview();}}
  else{{
    el.innerHTML = renderFiltered();
    const sb = document.getElementById("searchBox");
    if(sb){{sb.addEventListener("input",e=>{{searchTerm=e.target.value;render();const sb2=document.getElementById("searchBox");if(sb2){{sb2.focus();sb2.setSelectionRange(sb2.value.length,sb2.value.length);}}}});}}
  }}
  document.querySelectorAll(".filter-chip[data-filter]").forEach(b=>{{b.classList.toggle("active", b.dataset.filter===currentFilter);}});
}}
function setFilter(f){{currentFilter=f;searchTerm="";render();window.scrollTo(0,0);}}
document.querySelectorAll(".filter-chip[data-filter]").forEach(b=>{{b.addEventListener("click",()=>setFilter(b.dataset.filter));}});
render();
</script>"""

    return _page(
        f'{project.get("name","")} — Matriz de Rastreabilidade',
        body,
        "traceability",
        project,
        extra_css=_TRACE_CSS,
        script=script,
        data=data,
    )


# ──────────────────────────────────────────────────────────────────────
# roadmap.html — cycles with temporal axis
# ──────────────────────────────────────────────────────────────────────

_ROADMAP_CSS = """
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:8px}
@media(max-width:760px){.metrics{grid-template-columns:repeat(2,1fr)}}
.metric{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow)}
.metric .v{font-size:24px;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.metric .k{font-size:12px;color:var(--faint);font-weight:600;margin-top:4px;letter-spacing:.02em}
.metric .v.green{color:var(--green)} .metric .v.accent{color:var(--accent)}
.metric .sub{font-size:11px;color:var(--faint);margin-top:3px}
.flow{display:flex;align-items:stretch;gap:0;margin:22px 0 6px;overflow-x:auto;padding-bottom:6px}
.flow-step{flex:1 1 0;min-width:150px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 14px 12px;position:relative;box-shadow:var(--shadow)}
.flow-step + .flow-step{margin-left:22px}
.flow-step + .flow-step::before{content:"";position:absolute;left:-15px;top:50%;width:14px;height:2px;background:var(--border-strong)}
.flow-step + .flow-step::after{content:"\\25B6";position:absolute;left:-9px;top:50%;transform:translateY(-50%);color:var(--faint);font-size:10px}
.flow-step .fn{font-family:var(--font-mono);font-size:11px;color:var(--accent);font-weight:600}
.flow-step .ft{font-weight:700;font-size:14px;margin:2px 0 4px}
.flow-step .fg{font-size:12px;color:var(--muted);margin:0;line-height:1.45}
.flow-step .gate{margin-top:8px;font-size:11px;color:var(--amber);font-weight:600;display:flex;align-items:center;gap:4px}
.band{margin:34px 0 6px}
.band-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.band-title{font-size:18px;font-weight:700;letter-spacing:-.01em}
.band-tag{font-family:var(--font-mono);font-size:11px;color:var(--accent);background:var(--accent-soft);padding:3px 9px;border-radius:999px;font-weight:600}
.band-sub{font-size:13px;color:var(--muted);margin:0}
.timeline{position:relative;padding-left:38px;border-left:2px solid var(--border)}
.tl-item{position:relative;margin-bottom:18px}
.tl-item::before{content:"";position:absolute;left:-44px;top:6px;width:14px;height:14px;border-radius:50%;background:var(--surface);border:3px solid var(--accent);box-shadow:0 0 0 4px var(--bg)}
.tl-item.fix::before{border-color:var(--amber)}
.tl-item.demo::before{border-color:var(--green)}
.tl-item.infra::before{border-color:var(--blue)}
.tl-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 20px;box-shadow:var(--shadow);transition:border-color .15s, transform .15s}
.tl-card:hover{border-color:var(--border-strong);transform:translateY(-1px)}
.tl-top{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.tl-num{font-family:var(--font-mono);font-size:12px;font-weight:600;color:var(--faint);background:var(--surface-2);padding:2px 8px;border-radius:6px;border:1px solid var(--border)}
.tl-title{font-size:16px;font-weight:700;letter-spacing:-.01em;margin:0}
.tl-mod{font-family:var(--font-mono);font-size:11px;color:var(--accent);font-weight:600}
.tl-desc{font-size:13.5px;color:var(--muted);margin:0 0 10px;max-width:68ch}
.tl-meta{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:8px}
.pill.fix{background:rgba(176,107,0,.12);color:var(--amber)}
.pill.demo{background:rgba(43,108,176,.12);color:var(--blue)}
.artifacts{display:inline-flex;gap:5px;flex-wrap:wrap}
.artifacts code{font-size:10.5px;padding:1px 6px}
.artifacts a{font-size:10.5px;padding:1px 6px;font-family:var(--font-mono);background:var(--surface-2);border:1px solid var(--border);border-radius:5px;color:var(--muted);text-decoration:none}
.artifacts a:hover{border-color:var(--accent);color:var(--accent)}
.art-dead{font-size:10.5px;padding:1px 6px;font-family:var(--font-mono);background:var(--surface-2);border:1px solid var(--border);border-radius:5px;color:var(--faint)}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin:10px 0 0}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:10px;height:10px;border-radius:50%;border:2.5px solid var(--accent);background:var(--bg)}
.dot.fix{border-color:var(--amber)} .dot.demo{border-color:var(--green)} .dot.infra{border-color:var(--blue)}

/* Horizons */
.horizons{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:18px 0}
@media(max-width:760px){.horizons{grid-template-columns:1fr}}
.horizon{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px 22px;box-shadow:var(--shadow)}
.horizon .h-label{font-size:13px;font-weight:700;margin-bottom:8px}
.horizon .h-title{font-size:15px;font-weight:650;margin-bottom:12px;color:var(--ink)}
.horizon ul{margin:0;padding-left:18px}
.horizon li{font-size:13px;color:var(--muted);margin-bottom:6px}
.horizon.done{{border-left:3px solid var(--green)}}
.horizon.now{{border-left:3px solid var(--accent)}}
.horizon.later{{border-left:3px solid var(--amber)}}

/* Dependencies */
.deps{{margin:18px 0}}
.dep-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px}}
.dep-row:last-child{{border-bottom:none}}
.dep-from{{font-family:var(--font-mono);font-size:12px;font-weight:600;color:var(--accent);background:var(--accent-soft);padding:3px 9px;border-radius:7px}}
.dep-arrow{{color:var(--faint);font-size:14px}}
.dep-to{{font-family:var(--font-mono);font-size:12px;font-weight:600;color:var(--muted);background:var(--surface-2);border:1px solid var(--border);padding:3px 9px;border-radius:7px}}
.dep-why{{color:var(--muted);font-size:12.5px;margin-left:8px}}

/* Gates strip */
.gates{{display:flex;align-items:center;gap:5px;margin-top:10px;flex-wrap:wrap}}
.glabel{{font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-right:4px}}
.gate-cell{{font-family:var(--font-mono);font-size:10.5px;font-weight:600;color:var(--green);background:rgba(26,122,76,.1);padding:2px 7px;border-radius:5px}}
.gate-cell.b{{color:var(--accent);background:var(--accent-soft)}}

.callout.warn{{border-left-color:var(--amber);background:rgba(176,107,0,.06)}}
"""


def _render_roadmap(data: dict, project: dict) -> str:
    rm = data.get("roadmap", {})
    specs = data.get("specs", [])
    adrs = data.get("adrs", [])
    journeys = data.get("journeys", [])
    skills = data.get("skills", [])
    scripts = data.get("scripts", [])

    # ── Always sanitize bands/cycles gates and deps from generate.py ──
    # Gates should be F0✓...F5○, not raw text
    for band in rm.get("bands", []):
        for cyc in band.get("cycles", []):
            # Check if gates are malformed (long text instead of F0✓ format)
            gates = cyc.get("gates", [])
            needs_fix = any(len(g.get("text", "")) > 5 for g in gates) if gates else True
            if needs_fix or not gates:
                # Determine status from cycle meta or spec
                cyc_status = ""
                for mt in cyc.get("meta", []):
                    if "aprovada" in mt.get("text", "").lower() or "ok" in mt.get("cls", ""):
                        cyc_status = "aprovada"
                # Also check cycle cls
                if cyc.get("cls") == "fix":
                    cyc_status = "rascunho"
                f2 = "✓" if cyc_status == "aprovada" else "○"
                f1 = "✓" if cyc_status in ("aprovada", "rascunho") else "○"
                cyc["gates"] = [
                    {"text": "F0✓"},
                    {"text": f"F1{f1}"},
                    {"text": f"F2{f2}"},
                    {"text": "F3○", "b": True},
                    {"text": "F4○"},
                    {"text": "F5○"},
                ]

    # ── Always sanitize deps — replace raw text with proper cycle IDs ──
    raw_deps = rm.get("dependencies", [])
    has_raw_deps = any(
        any(len(str(t)) > 30 for t in d.get("to", []))
        for d in raw_deps
    )
    if has_raw_deps or (not raw_deps and specs):
        # Rebuild deps from specs as cycle-to-cycle relations
        # Extract just the numeric prefix from spec IDs (e.g., "001-fundacao" → "001")
        def _cycle_num(s):
            sid = s.get("spec", s.get("id", ""))
            # Extract leading digits
            num = ""
            for c in sid:
                if c.isdigit(  ):
                    num += c
                else:
                    break
            return num or sid

        deps = []
        if len(specs) >= 2:
            for i, s in enumerate(specs[1:], 1):
                prev = specs[i - 1]
                s_num = _cycle_num(s)
                p_num = _cycle_num(prev)
                deps.append({
                    "from": f"Ciclo {p_num}",
                    "to": [f"Ciclo {s_num}"],
                    "why": f"{s.get('name', s_num)} depende de {prev.get('name', p_num)}",
                })
        # Add implementation dependency
        if specs:
            last_spec = specs[-1]
            last_num = _cycle_num(last_spec)
            deps.append({
                "from": f"Ciclo {last_num}",
                "to": ["Ciclo 004+"],
                "why": "Implementação depende de todos os specs aprovados",
            })
        rm["dependencies"] = deps

    # ── Auto-populate bands from specs when empty ──
    if not rm.get("bands") and specs:
        cycles = []
        for s in specs:
            s_status = s.get("status", "")
            s_cls = ""
            if s_status.lower() in ("rascunho", "draft"):
                s_cls = "fix"
            elif s_status.lower() in ("aprovada", "accepted", "done"):
                s_cls = ""
            spec_dir = s.get("specDir", "")
            artifacts_html = []
            for art in s.get("artifacts", []):
                art_name = art if isinstance(art, str) else art.get("name", "")
                art_path = art if isinstance(art, str) else art.get("path", f"../../specs/{spec_dir}/{art_name}")
                artifacts_html.append({"href": art_path, "text": art_name})
            f2 = "✓" if s_status.lower() in ("aprovada", "accepted", "done") else "○"
            cycles.append({
                "cls": s_cls,
                "num": s.get("spec", s.get("id", "")),
                "title": s.get("name", ""),
                "mod": s.get("id", ""),
                "desc": s.get("vision", s.get("description", "")),
                "meta": [
                    {"cls": "ok" if s_status.lower() in ("aprovada", "accepted", "done") else "wip",
                     "text": f"✓ {s_status}" if s_status else ""},
                    {"cls": "muted", "text": f"{s.get('rf', 0)} RFs"},
                ],
                "artifacts": [{"href": f"../../specs/{spec_dir}/spec.md", "text": "spec"}] + artifacts_html,
                "gates": [
                    {"text": "F0✓"},
                    {"text": "F1✓"},
                    {"text": f"F2{f2}"},
                    {"text": "F3○", "b": True},
                    {"text": "F4○"},
                    {"text": "F5○"},
                ],
            })
        rm["bands"] = [{
            "title": "Specs (Ciclos)",
            "tag": f"{len(specs)} ciclos",
            "sub": "Especificação — pré-implementação" if not data.get("modules") else "Módulos de domínio",
            "cycles": cycles,
        }]

    if not rm.get("metrics"):
        rm["metrics"] = []
        rm["metrics"].append({"v": str(len(specs)), "k": "Specs", "sub": "ciclos", "class": "green" if specs else ""})
        rm["metrics"].append({"v": str(len(adrs)), "k": "ADRs", "sub": "decisões"})
        rm["metrics"].append({"v": str(len(skills)), "k": "Skills", "sub": "artefatos"})
        rm["metrics"].append({"v": str(len(journeys)), "k": "Jornadas", "sub": "demos"})

    if not rm.get("phases"):
        rm["phases"] = [
            {"fn": "F0", "ft": "Inventário", "fg": "Ler documentação legada e extrair entidades, fluxos, telas.", "gate": "nada se builda antes"},
            {"fn": "F1", "ft": "Spec", "fg": "Para cada módulo, spec.md — seções padronizadas.", "gate": "RF + RNF completos"},
            {"fn": "F2", "ft": "Plan & Tasks", "fg": "plan.md + tasks.md. Tarefa rastreia RF/RNF.", "gate": "toda task → um RF/RNF"},
            {"fn": "F3", "ft": "Build (TDD)", "fg": "domain → application → infrastructure → api → tests.", "gate": "domínio puro, mutation"},
            {"fn": "F4", "ft": "Gauntlet", "fg": "Crítico cego compara vs. legado, tela a tela.", "gate": "crítico escolhe o nosso"},
            {"fn": "F5", "ft": "Deploy", "fg": "Deploy + migrations + seeds.", "gate": "health 200, E2E"},
        ]

    if not rm.get("horizons"):
        aprovadas = [s for s in specs if s.get("status", "").lower() in ("aprovada", "accepted", "done")]
        rascunhos = [s for s in specs if s.get("status", "").lower() in ("rascunho", "draft")]
        rm["horizons"] = []
        if aprovadas:
            rm["horizons"].append({"label": "✅ Concluído", "title": f"{len(aprovadas)} specs aprovadas", "items": [f"{s.get('spec','')} {s.get('name','')}" for s in aprovadas], "cls": "done"})
        if rascunhos:
            rm["horizons"].append({"label": "🔹 Now", "title": "Specs em rascunho", "items": [f"{s.get('spec','')} {s.get('name','')}" for s in rascunhos], "cls": "now"})
        rm["horizons"].append({"label": "🔜 Next", "title": "Implementação", "items": ["Construção TDD", "Gauntlet cego", "Deploy"], "cls": "later"})

    if not rm.get("legend"):
        rm["legend"] = [
            {"cls": "", "label": "Spec (aprovada)"},
            {"cls": "fix", "label": "Spec (rascunho)"},
            {"cls": "demo", "label": "Demo / jornada"},
        ]

    # Metrics
    rm_metrics = rm.get("metrics", [])
    metrics_html = '<div class="metrics">'
    for mt in rm_metrics:
        cls = mt.get("class", "")
        metrics_html += f'<div class="metric"><div class="v {cls}">{_e(mt.get("v",""))}</div><div class="k">{_e(mt.get("k",""))}</div>'
        if mt.get("sub"):
            metrics_html += f'<div class="sub">{_e(mt.get("sub",""))}</div>'
        metrics_html += '</div>'
    metrics_html += '</div>'

    # Horizons
    horizons = rm.get("horizons", [])
    horizons_html = '<div class="horizons">'
    for h in horizons:
        cls = h.get("cls", "")
        items = "".join(f"<li>{item}</li>" for item in h.get("items", []))
        horizons_html += f'<div class="horizon {cls}"><div class="h-label">{_e(h.get("label",""))}</div><div class="h-title">{_e(h.get("title",""))}</div><ul>{items}</ul></div>'
    horizons_html += '</div>'

    # Phases (flow strip)
    phases = rm.get("phases", [])
    flow_html = '<div class="flow">'
    for p in phases:
        flow_html += f'<div class="flow-step"><div class="fn">{_e(p.get("fn",""))}</div><div class="ft">{_e(p.get("ft",""))}</div><div class="fg">{p.get("fg","")}</div><div class="gate">⏳ Gate: {_e(p.get("gate",""))}</div></div>'
    flow_html += '</div>'

    # Dependencies
    deps = rm.get("dependencies", [])
    deps_html = '<div class="deps">'
    for d in deps:
        to_tags = "".join(f'<span class="dep-to">{_e(t)}</span>' for t in d.get("to", []))
        deps_html += f'<div class="dep-row"><span class="dep-from">{_e(d.get("from",""))}</span><span class="dep-arrow">→</span>{to_tags}<span class="dep-why">{d.get("why","")}</span></div>'
    deps_html += '</div>'

    # Legend
    legend = rm.get("legend", [])
    legend_html = '<div class="legend">'
    for item in legend:
        cls = item.get("cls", "")
        legend_html += f'<span><span class="dot {cls}"></span> {_e(item.get("label",""))}</span>'
    legend_html += '</div>'

    # Bands with timeline cycles
    bands = rm.get("bands", [])
    bands_html = ""
    for band in bands:
        band_cycles = band.get("cycles", [])
        timeline_html = '<div class="timeline">'
        for cyc in band_cycles:
            cls = cyc.get("cls", "")
            num = cyc.get("num", "")
            title = cyc.get("title", "")
            mod = cyc.get("mod", "")
            desc = cyc.get("desc", "")
            meta = cyc.get("meta", [])
            artifacts = cyc.get("artifacts", [])

            meta_html = ""
            for m_item in meta:
                mcls = m_item.get("cls", "")
                meta_html += f'<span class="pill {mcls}">{m_item.get("text","")}</span>'

            art_html = '<span class="artifacts">'
            for a in artifacts:
                if a.get("href"):
                    art_html += f'<a href="{_e(a["href"])}">{_e(a.get("text",""))}</a>'
                else:
                    art_html += f'<span class="art-dead">{_e(a.get("text",""))}</span>'
            art_html += '</span>'

            # Gates strip
            gates = cyc.get("gates", [])
            gates_html = '<div class="gates"><span class="glabel">Gates</span>'
            for g in gates:
                gcls = " b" if g.get("b") else ""
                gates_html += f'<span class="gate-cell{gcls}">{_e(g.get("text",""))}</span>'
            gates_html += '</div>'

            timeline_html += f"""
      <div class="tl-item {cls}">
        <div class="tl-card">
          <div class="tl-top"><span class="tl-num">{num}</span><span class="tl-title">{title}</span><span class="tl-mod">{mod}</span></div>
          <p class="tl-desc">{desc}</p>
          <div class="tl-meta">{meta_html}{art_html}</div>
          {gates_html}
        </div>
      </div>"""
        timeline_html += '</div>'

        bands_html += f"""
  <div class="band">
    <div class="band-head">
      <span class="band-title">{_e(band.get("title",""))}</span>
      <span class="band-tag">{_e(band.get("tag",""))}</span>
      <span class="band-sub">{band.get("sub","")}</span>
    </div>
    {timeline_html}
  </div>"""

    # Intro
    eyebrow = rm.get("eyebrow", "Roadmap")
    title = rm.get("title", "Roadmap")
    lede = rm.get("lede", "")
    callout = rm.get("callout", "")
    honesty = rm.get("honesty", "")
    footer = rm.get("footer", "")

    body = f"""
  <p class="eyebrow">{eyebrow}</p>
  <h1>{title}</h1>
  <p class="lede">{lede}</p>
  <div class="callout">{callout}</div>
  <h2>Estado quantificado</h2>
  {metrics_html}
  <h2>Horizonte — Now / Next / Later</h2>
  {horizons_html}
  <h2>As 6 fases do MAESTRO (per-corridas por cada ciclo)</h2>
  {flow_html}
  <h2>Dependências entre ciclos</h2>
  {deps_html}
  {legend_html}
  <h2>Linha do tempo dos ciclos</h2>
  {bands_html}
  <div class="divider"></div>
  <div class="callout warn">{honesty}</div>
  <p class="faint" style="font-size:12px">{footer}</p>
"""

    return _page(
        f'{project.get("name","")} — Roadmap',
        body,
        "roadmap",
        project,
        extra_css=_ROADMAP_CSS,
        data=data,
    )


# ──────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────

def render(data: dict, output_dir: str | Path) -> None:
    """Render the documentation site from JSON data.

    Args:
        data: JSON dict with keys: project, overview, taxonomy, workflow,
              adrs, metrics, modules, traceability, roadmap.
        output_dir: Directory to write HTML files to.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    project = data.get("project", {})
    # Count modules from code modules, or specs if pre-implementation
    n_mods = len(data.get("modules", []))
    if not n_mods:
        n_mods = len(data.get("specs", []))
    project["n_modules"] = str(n_mods) if n_mods else ""
    project["n_adrs"] = str(len(data.get("adrs", [])))

    # styles.css — copy from templates
    templates_dir = Path(__file__).parent / "templates"
    css_src = templates_dir / "styles.css"
    css_dst = out / "styles.css"
    if css_src.exists():
        shutil.copy2(css_src, css_dst)
    else:
        # Fallback: write minimal CSS
        css_dst.write_text("/* styles.css — template not found */\n", encoding="utf-8")

    # index.html
    (out / "index.html").write_text(
        _render_index(data, project), encoding="utf-8"
    )

    # modules.html
    (out / "modules.html").write_text(
        _render_modules(data, project), encoding="utf-8"
    )

    # traceability.html
    (out / "traceability.html").write_text(
        _render_traceability(data, project), encoding="utf-8"
    )

    # roadmap.html
    (out / "roadmap.html").write_text(
        _render_roadmap(data, project), encoding="utf-8"
    )


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Render spec-to-code-docs HTML site")
    parser.add_argument("input", help="Path to JSON data file")
    parser.add_argument("--output", "-o", default="docs/product-site", help="Output directory")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    render(data, args.output)
    print(f"Site rendered to {args.output}/")


if __name__ == "__main__":
    main()
