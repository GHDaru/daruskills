#!/usr/bin/env bash
# spec-to-code-docs — installer
# Copies the skill into a project's .claude/skills/ so Claude Code discovers it.
# Usage: ./install.sh [target-project-dir]  (default: current dir)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="spec-to-code-docs"
TARGET="${1:-.}"
DEST="$TARGET/.claude/skills/$SKILL_NAME"

if [ ! -d "$TARGET" ]; then
  echo "Error: target directory '$TARGET' does not exist." >&2
  exit 1
fi

mkdir -p "$DEST"
cp -r "$SCRIPT_DIR"/{SKILL.md,generate.py,render.py,templates} "$DEST/"
# Copy optional files if they exist
[ -f "$SCRIPT_DIR/target-inventory.md" ] && cp "$SCRIPT_DIR/target-inventory.md" "$DEST/" || true
[ -f "$SCRIPT_DIR/README.md" ] && cp "$SCRIPT_DIR/README.md" "$DEST/" || true

echo "✓ Skill '$SKILL_NAME' installed to: $DEST"
echo ""
echo "Usage in the target project:"
echo "  python .claude/skills/$SKILL_NAME/generate.py . --output docs/product-site/data.json"
echo "  python .claude/skills/$SKILL_NAME/render.py docs/product-site/data.json --output docs/product-site"
echo ""
echo "Or just ask Claude: 'document this project with spec-to-code-docs'"
