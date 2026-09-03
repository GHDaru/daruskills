# spec-to-code-docs — installer (Windows PowerShell)
# Copies the skill into a project's .claude\skills\ so Claude Code discovers it.
# Usage: .\install.ps1 [target-project-dir]  (default: current dir)
param(
    [string]$Target = "."
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillName = "spec-to-code-docs"
$Dest = Join-Path $Target ".claude\skills\$SkillName"

if (-not (Test-Path $Target)) {
    Write-Error "Target directory '$Target' does not exist."
    exit 1
}

New-Item -ItemType Directory -Path $Dest -Force | Out-Null

Copy-Item (Join-Path $ScriptDir "SKILL.md") $Dest -Force
Copy-Item (Join-Path $ScriptDir "generate.py") $Dest -Force
Copy-Item (Join-Path $ScriptDir "render.py") $Dest -Force
Copy-Item (Join-Path $ScriptDir "templates") $Dest -Recurse -Force

# Optional files
$optional = @("target-inventory.md", "README.md")
foreach ($f in $optional) {
    $src = Join-Path $ScriptDir $f
    if (Test-Path $src) { Copy-Item $src $Dest -Force }
}

Write-Host "✓ Skill '$SkillName' installed to: $Dest" -ForegroundColor Green
Write-Host ""
Write-Host "Usage in the target project:"
Write-Host "  python .claude\skills\$SkillName\generate.py . --output docs\product-site\data.json"
Write-Host "  python .claude\skills\$SkillName\render.py docs\product-site\data.json --output docs\product-site"
Write-Host ""
Write-Host "Or just ask Claude: 'document this project with spec-to-code-docs'" -ForegroundColor Cyan
