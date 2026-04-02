@echo off
REM ArXiv MCP Server Setup Script for Windows (Native)
REM Run: ARXIV_SETUP.bat

setlocal enabledelayedexpansion

echo.
echo ==========================================
echo ArXiv MCP Server Setup for Claude Code
echo ==========================================
echo.

REM Check Python
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo OK: %PYTHON_VERSION% found
echo.

REM Check/Install Poetry
echo [2/6] Setting up Poetry...
poetry --version >nul 2>&1
if errorlevel 1 (
    echo Installing Poetry...
    pip install poetry --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install Poetry
        pause
        exit /b 1
    )
) else (
    echo OK: Poetry already installed
)
echo.

REM Clone Repository
echo [3/6] Cloning arxiv-mcp-server repository...
set REPO_PATH=learn\arxiv-mcp-server
if exist "%REPO_PATH%" (
    echo WARNING: Repository already exists at %REPO_PATH%
    set /p OVERWRITE="Overwrite? (y/n): "
    if /i "!OVERWRITE!"=="y" (
        rmdir /s /q "%REPO_PATH%"
        git clone https://github.com/1Dark134/arxiv-mcp-server.git "%REPO_PATH%"
    )
) else (
    git clone https://github.com/1Dark134/arxiv-mcp-server.git "%REPO_PATH%"
)
echo OK: Repository cloned
echo.

REM Install Dependencies
echo [4/6] Installing dependencies with Poetry...
cd "%REPO_PATH%"
call poetry install --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    cd ../..
    pause
    exit /b 1
)
cd ../..
echo OK: Dependencies installed
echo.

REM Create Cache Directory
echo [5/6] Creating cache directory...
if not exist "%USERPROFILE%\.arxiv-cache" (
    mkdir "%USERPROFILE%\.arxiv-cache"
)
echo OK: Cache directory created at %USERPROFILE%\.arxiv-cache
echo.

REM Update Claude Code Settings
echo [6/6] Updating Claude Code settings...
if not exist "%USERPROFILE%\.claude" (
    mkdir "%USERPROFILE%\.claude"
)

set SETTINGS_FILE=%USERPROFILE%\.claude\settings.json

if not exist "%SETTINGS_FILE%" (
    echo Creating new settings.json...
    (
        echo {
        echo   "mcpServers": {
        echo     "arxiv-mcp-server": {
        echo       "command": "python",
        echo       "args": [
        echo         "-m",
        echo         "arxiv_mcp_server"
        echo       ],
        echo       "env": {
        echo         "ARXIV_CACHE_DIR": "%USERPROFILE%\.arxiv-cache",
        echo         "ARXIV_API_TIMEOUT": "30",
        echo         "ARXIV_MAX_RESULTS": "100"
        echo       }
        echo     }
        echo   }
        echo }
    ) > "%SETTINGS_FILE%"
    echo OK: Created new settings.json
) else (
    echo WARNING: settings.json already exists
    echo Please manually add the following to %SETTINGS_FILE% if not present:
    echo.
    echo     "arxiv-mcp-server": {
    echo       "command": "python",
    echo       "args": ["-m", "arxiv_mcp_server"],
    echo       "env": {
    echo         "ARXIV_CACHE_DIR": "%USERPROFILE%\.arxiv-cache",
    echo         "ARXIV_API_TIMEOUT": "30",
    echo         "ARXIV_MAX_RESULTS": "100"
    echo       }
    echo     }
)
echo.

REM Verify Installation
echo ==========================================
echo Verification...
echo ==========================================
cd "%REPO_PATH%"
poetry run python -m arxiv_mcp_server --help >nul 2>&1
if errorlevel 1 (
    echo WARNING: Could not verify MCP server executable
) else (
    echo OK: MCP server executable verified
)
cd ../..
echo.

echo ==========================================
echo Setup Complete! OK
echo ==========================================
echo.
echo Next steps:
echo 1. Restart Claude Code (Ctrl+Shift+P ^> Reload)
echo 2. Check Settings ^> MCP Servers to verify arxiv-mcp-server is listed
echo 3. Test with: poetry run arxiv-mcp search --query "bitcoin" --limit 5
echo.
echo Documentation: learn\riset_renaisance\SETUP_ARXIV_MCP_SERVER.md
echo.

pause
