# daruskills

Coleção de skills Claude Code reutilizáveis — aplicáveis em qualquer projeto.

## Skills

### spec-to-code-docs
Gera um site de documentação navegável que rastreia da fonte de negócio (specs/legado) até o código — taxonomia, matriz de rastreabilidade, páginas por módulo, roadmap, workflow, design Linear-grade.

**Instalar:**
```bash
cd spec-to-code-docs && ./install.sh /path/to/your/project
```

**Usar (via Claude):** peça "document this project with spec-to-code-docs"

**Usar (CLI):**
```bash
python .claude/skills/spec-to-code-docs/generate.py . --output docs/product-site/data.json
python .claude/skills/spec-to-code-docs/render.py docs/product-site/data.json --output docs/product-site
```

Requer Python 3.12+ (stdlib only).
