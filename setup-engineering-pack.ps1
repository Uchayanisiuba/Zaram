# =====================================================
# Zaram Engineering Pack Setup
# Version 2.0
# =====================================================

$Root = "C:\Zaram"

Write-Host ""
Write-Host "==========================================="
Write-Host " Setting up Zaram Engineering Pack"
Write-Host "==========================================="
Write-Host ""

# Create directories
$Directories = @(
    "$Root\.ai",
    "$Root\.ai\skills",
    "$Root\.continue",
    "$Root\.continue\rules",
    "$Root\.continue\prompts",
    "$Root\.continue\commands"
)

foreach ($Dir in $Directories) {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
}

# Files to create/reset
$Files = @(

    # Engineering Handbook
    ".ai\00_PROJECT_BIBLE.md",
    ".ai\01_ARCHITECTURE.md",
    ".ai\02_UI_GUIDELINES.md",
    ".ai\03_MODEL_ROUTER.md",
    ".ai\04_MODEL_REGISTRY.md",
    ".ai\05_MEMORY_SYSTEM.md",
    ".ai\06_VOICE_ENGINE.md",
    ".ai\07_SKILL_SYSTEM.md",
    ".ai\08_SKILL_SDK.md",
    ".ai\09_SKILL_MARKETPLACE.md",
    ".ai\10_SECURITY_MODEL.md",
    ".ai\11_API_SPEC.md",
    ".ai\12_DATABASE_SCHEMA.md",
    ".ai\13_CODING_STANDARDS.md",
    ".ai\14_ROADMAP.md",
    ".ai\15_CURRENT_SPRINT.md",
    ".ai\16_UNREAL_INTEGRATION.md",

    # Skill Specifications
    ".ai\skills\TRADING_SKILL.md",
    ".ai\skills\UNREAL_SKILL.md",
    ".ai\skills\GITHUB_SKILL.md",
    ".ai\skills\EMAIL_SKILL.md",
    ".ai\skills\CALENDAR_SKILL.md",
    ".ai\skills\BUSINESS_SKILL.md",

    # Continue Rules
    ".continue\rules\zaram.md",
    ".continue\rules\skills.md",

    # Continue Prompts
    ".continue\prompts\implement.md",
    ".continue\prompts\review.md",
    ".continue\prompts\debug.md",

    # Continue Commands
    ".continue\commands\build.md",
    ".continue\commands\review.md",
    ".continue\commands\refactor.md"
)

foreach ($File in $Files) {

    $FullPath = Join-Path $Root $File

    if (Test-Path $FullPath) {
        Remove-Item $FullPath -Force
    }

    New-Item -ItemType File -Path $FullPath | Out-Null

    Write-Host "Created: $File"
}

Write-Host ""
Write-Host "==========================================="
Write-Host " Engineering Pack Ready"
Write-Host "==========================================="
Write-Host ""
Write-Host "Next:"
Write-Host "1. Open each Markdown file."
Write-Host "2. Paste the generated documentation."
Write-Host "3. Commit to Git."
Write-Host ""