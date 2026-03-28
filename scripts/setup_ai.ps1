param(
    [string]$Model = "qwen3:4b"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Missing virtual environment at $python"
    Write-Host "Create it first, then run this script again."
    exit 1
}

Write-Host "Installing Python dependencies..."
& $python -m pip install -r (Join-Path $repoRoot "requirements.txt")

Write-Host "Training HR attrition model..."
& $python (Join-Path $repoRoot "ai\train_attrition.py")

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Pulling Ollama model: $Model"
    ollama pull $Model
    Write-Host "Ollama model ready."
} else {
    Write-Host "Ollama CLI not found."
    Write-Host "Install Ollama first, then run: ollama pull $Model"
}

Write-Host "Setup completed."
