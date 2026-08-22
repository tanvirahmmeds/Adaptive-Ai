<# 
.SYNOPSIS
    Adaptive Framework Installer for Windows (PowerShell)
.DESCRIPTION
    Installs Adaptive Framework on Windows with all dependencies
#>

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\adaptive-framework",
    [string]$DataDir = "$env:USERPROFILE\.adaptive_framework",
    [switch]$InstallSystemDeps,
    [switch]$NoPath
)

$ErrorActionPreference = "Stop"

# Colors
$Green = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Red = [ConsoleColor]::Red
$Blue = [ConsoleColor]::Cyan

function Write-LogInfo { param($msg) Write-Host "[INFO] $msg" -ForegroundColor $Blue }
function Write-LogSuccess { param($msg) Write-Host "[SUCCESS] $msg" -ForegroundColor $Green }
function Write-LogWarn { param($msg) Write-Host "[WARN] $msg" -ForegroundColor $Yellow }
function Write-LogError { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor $Red }

Write-Host @"
╔══════════════════════════════════════════╗
║   Adaptive Framework Installer v0.1.0   ║
║   Self-improving AI Agent Platform       ║
╚══════════════════════════════════════════╝
"@ -ForegroundColor $Blue

# Check PowerShell version
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-LogError "PowerShell 5.1+ required"
    exit 1
}

# Check Python
Write-LogInfo "Checking Python installation..."
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
} else {
    Write-LogError "Python not found. Please install Python 3.10+ from https://python.org"
    exit 1
}

$pythonVersion = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$major = [int]($pythonVersion.Split('.')[0])
$minor = [int]($pythonVersion.Split('.')[1])

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-LogError "Python 3.10+ required, found $pythonVersion"
    exit 1
}
Write-LogSuccess "Python $pythonVersion found"

# Install system dependencies if requested
if ($InstallSystemDeps) {
    Write-LogInfo "Installing system dependencies..."
    
    # Check for winget
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-LogInfo "Installing via winget..."
        winget install --id Git.Git --silent --accept-source-agreements --accept-package-agreements 2>$null
        winget install --id Microsoft.VisualStudioCode --silent --accept-source-agreements --accept-package-agreements 2>$null
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-LogInfo "Installing via Chocolatey..."
        choco install git vscode -y
    } else {
        Write-LogWarn "No package manager found. Please install Git manually from https://git-scm.com"
    }
}

# Create directories
Write-LogInfo "Creating directories..."
$installDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InstallDir)
$dataDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DataDir)

New-Item -ItemType Directory -Force -Path $installDir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path "$dataDir\extensions" | Out-Null
New-Item -ItemType Directory -Force -Path "$dataDir\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$dataDir\cache" | Out-Null

Write-LogSuccess "Directories created"

# Create virtual environment
Write-LogInfo "Creating virtual environment..."
$venvDir = "$dataDir\venv"
& $pythonCmd -m venv $venvDir
Write-LogSuccess "Virtual environment created at $venvDir"

# Activate and upgrade pip
$venvPython = "$venvDir\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip setuptools wheel

# Install Adaptive Framework
Write-LogInfo "Installing Adaptive Framework..."
if (Test-Path "pyproject.toml") {
    Write-LogInfo "Installing from local source..."
    & $venvPython -m pip install -e ".[all]"
} else {
    Write-LogInfo "Installing from PyPI..."
    & $venvPython -m pip install "adaptive-framework[all]"
}
Write-LogSuccess "Adaptive Framework installed"

# Create launcher scripts
Write-LogInfo "Creating launcher scripts..."

# Main CLI launcher (batch)
$cliLauncher = @"
@echo off
REM Adaptive Framework CLI Launcher
set DATA_DIR=$dataDir
set VENV_DIR=$venvDir
call "%VENV_DIR%\Scripts\activate.bat"
adaptive-framework %*
"@
$cliLauncher | Out-File -Encoding ASCII "$installDir\adaptive.bat"

# Main CLI launcher (PowerShell)
$cliLauncherPs1 = @"
# Adaptive Framework CLI Launcher
`$env:DATA_DIR = "$dataDir"
`$env:VENV_DIR = "$venvDir"
& "`$venvDir\Scripts\Activate.ps1"
adaptive-framework `@args
"@
$cliLauncherPs1 | Out-File -Encoding UTF8 "$installDir\adaptive.ps1"

# Web UI launcher
$webLauncher = @"
@echo off
REM Adaptive Framework Web UI Launcher
set DATA_DIR=$dataDir
set VENV_DIR=$venvDir
call "%VENV_DIR%\Scripts\activate.bat"
adaptive-framework-web %*
"@
$webLauncher | Out-File -Encoding ASCII "$installDir\adaptive-web.bat"

# GUI launcher
$guiLauncher = @"
@echo off
REM Adaptive Framework GUI Launcher
set DATA_DIR=$dataDir
set VENV_DIR=$venvDir
call "%VENV_DIR%\Scripts\activate.bat"
adaptive-framework-gui %*
"@
$guiLauncher | Out-File -Encoding ASCII "$installDir\adaptive-gui.bat"

# Agent CLI launcher
$agentLauncher = @"
@echo off
REM Adaptive Framework Agent CLI Launcher
set DATA_DIR=$dataDir
set VENV_DIR=$venvDir
call "%VENV_DIR%\Scripts\activate.bat"
adaptive-framework-agent %*
"@
$agentLauncher | Out-File -Encoding ASCII "$installDir\adaptive-agent.bat"

Write-LogSuccess "Launchers created in $installDir"

# Initialize data directory
Write-LogInfo "Initializing data directory..."
$configPath = "$dataDir\config.yaml"
$config = @"
# Adaptive Framework Configuration
model:
  provider: "auto"
  name: "auto"

tools:
  enabled:
    - "file_ops"
    - "shell"
    - "memory"
    - "learning"
    - "feedback"
    - "mcp"
    - "agent_loop"

skills:
  auto_create: true
  auto_improve: true

memory:
  backend: "sqlite"
  vector_enabled: true
  consolidation_interval: 3600

mcp:
  enabled: true
  servers: {}

webui:
  host: "0.0.0.0"
  port: 8080

gui:
  theme: "dark"
  window_size: "1200x800"

logging:
  level: "INFO"
  file: "logs/adaptive.log"
"@
$config | Out-File -Encoding UTF8 $configPath
Write-LogSuccess "Data directory initialized at $dataDir"

# Setup PATH
if (-not $NoPath) {
    Write-LogInfo "Setting up PATH..."
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$installDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$installDir", "User")
        Write-LogSuccess "Added $installDir to user PATH"
        Write-LogWarn "Please restart your terminal or run: refreshenv"
    } else {
        Write-LogInfo "PATH already configured"
    }
}

# Verify installation
Write-LogInfo "Verifying installation..."
$commands = @("adaptive.bat", "adaptive-web.bat", "adaptive-gui.bat", "adaptive-agent.bat")
foreach ($cmd in $commands) {
    $path = "$installDir\$cmd"
    if (Test-Path $path) {
        Write-LogSuccess "Launcher $cmd ready"
    } else {
        Write-LogError "Launcher $cmd missing"
    }
}

# Test CLI
try {
    & "$installDir\adaptive.bat" doctor 2>&1 | Select-String "Python" | Out-Null
    Write-LogSuccess "CLI working correctly"
} catch {
    Write-LogWarn "CLI test had issues"
}

Write-Host @"
╔══════════════════════════════════════════╗
║   Installation Complete!                 ║
╚══════════════════════════════════════════╝
"@ -ForegroundColor $Green

Write-Host @"
Next steps:
  1. Restart your terminal or run: refreshenv
  2. Run 'adaptive.bat doctor' to verify
  3. Run 'adaptive.bat run "your goal"' to start
  4. Run 'adaptive-web.bat' for Web UI
  5. Run 'adaptive-gui.bat' for Desktop GUI

Data directory: $dataDir
Config file: $configPath
Launchers: $installDir
"@ -ForegroundColor $Green