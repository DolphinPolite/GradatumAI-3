<#
PowerShell helper to initialize a local git repository, stage changes and create a commit.

Usage:
  ./scripts/prepare_git.ps1 -Message "Your commit message"

If no message is provided the script will use the text from COMMIT_MESSAGE.txt.
This script does NOT add any remote or push; run the printed instructions afterwards.
#>

param(
    [string]$Message = "",
    [switch]$ForceInit
)

Set-StrictMode -Version Latest

function Ensure-Git {
    try {
        git --version | Out-Null
        return $true
    } catch {
        Write-Error "Git not found in PATH. Install Git and re-run this script."
        exit 1
    }
}

if (-not (Ensure-Git)) { exit 1 }

$root = Resolve-Path ".." -Relative | Split-Path -Parent
Push-Location $PSScriptRoot

if (-not (Test-Path .git) -or $ForceInit) {
    Write-Host "Initializing git repository..."
    git init
} else {
    Write-Host "Git repository already initialized."
}

if (-not (Test-Path "../.gitignore")) {
    Write-Host "No .gitignore found in repo root. Please create one or edit the existing .gitignore."
} else {
    Write-Host ".gitignore present."
}

Write-Host "Staging changes (respects .gitignore)..."
git add -A

if (-not $Message) {
    if (Test-Path "../COMMIT_MESSAGE.txt") {
        $Message = Get-Content "../COMMIT_MESSAGE.txt" -Raw
    } else {
        $Message = "Initial commit: prepared repository"
    }
}

Write-Host "Creating commit..."
try {
    git commit -m $Message
    Write-Host "Commit created successfully."
} catch {
    Write-Warning "No changes to commit or commit failed: $_"
}

Write-Host "Next steps (example):"
Write-Host " 1) Create remote on GitHub (or use your own remote)."
Write-Host "    Using gh CLI: gh repo create <owner>/<repo> --public --source=. --remote=origin --push"
Write-Host " 2) Or add a remote manually: git remote add origin <URL> && git push -u origin main"

Pop-Location
