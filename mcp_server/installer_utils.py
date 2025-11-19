"""
Generate installer scripts for automated MCP server installation
"""
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from .claude_desktop_utils import generate_standalone_server_script



def generate_windows_installer(server_name: str) -> str:
    """Generate Windows batch installer script"""
    
    return f"""@echo off
setlocal enabledelayedexpansion

echo ========================================
echo MCP Server Auto-Installer (Windows)
echo Server: {server_name}
echo ========================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "SERVER_NAME={server_name}"

REM Set installation directory
set "INSTALL_DIR=%APPDATA%\\MCPServers\\%SERVER_NAME%"
echo Installing to: %INSTALL_DIR%
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

REM Create installation directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo [1/5] Creating virtual environment...
python -m venv "%INSTALL_DIR%\\.venv"
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo     Virtual environment created successfully

echo [2/5] Installing dependencies...
"%INSTALL_DIR%\\.venv\\Scripts\\python.exe" -m pip install --upgrade pip --quiet
"%INSTALL_DIR%\\.venv\\Scripts\\python.exe" -m pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo     Dependencies installed successfully

echo [3/5] Copying server files...
copy "%SCRIPT_DIR%*.yaml" "%INSTALL_DIR%\\" >nul
copy "%SCRIPT_DIR%*_server.py" "%INSTALL_DIR%\\" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy server files
    pause
    exit /b 1
)
echo     Server files copied successfully

echo [4/5] Backing up Claude Desktop config...
set "CLAUDE_CONFIG=%APPDATA%\\Claude\\claude_desktop_config.json"
if exist "%CLAUDE_CONFIG%" (
    set "BACKUP_NAME=claude_desktop_config.json.backup.%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
    set "BACKUP_NAME=!BACKUP_NAME: =0!"
    copy "%CLAUDE_CONFIG%" "%APPDATA%\\Claude\\!BACKUP_NAME!" >nul
    echo     Config backed up to: !BACKUP_NAME!
) else (
    echo     No existing config found (will create new)
)

echo [5/5] Updating Claude Desktop configuration...
"%INSTALL_DIR%\\.venv\\Scripts\\python.exe" "%SCRIPT_DIR%update_claude_config.py" "%SERVER_NAME%" "%INSTALL_DIR%"
if errorlevel 1 (
    echo ERROR: Failed to update Claude Desktop config
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Server installed to: %INSTALL_DIR%
echo Virtual environment: %INSTALL_DIR%\\.venv
echo.
echo NEXT STEPS:
echo 1. Restart Claude Desktop
echo 2. Your MCP tools will be available in Claude
echo.
echo To uninstall, delete: %INSTALL_DIR%
echo and remove the server entry from Claude Desktop config
echo.
pause
"""


def generate_unix_installer(server_name: str) -> str:
    """Generate Unix/macOS shell installer script"""
    
    return f"""#!/bin/bash

echo "========================================"
echo "MCP Server Auto-Installer (macOS/Linux)"
echo "Server: {server_name}"
echo "========================================"
echo

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" && pwd )"
SERVER_NAME="{server_name}"

# Set installation directory based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    INSTALL_DIR="$HOME/.mcp_servers/$SERVER_NAME"
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
else
    # Linux
    INSTALL_DIR="$HOME/.mcp_servers/$SERVER_NAME"
    CLAUDE_CONFIG="$HOME/.config/claude/claude_desktop_config.json"
fi

echo "Installing to: $INSTALL_DIR"
echo

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "${{RED}}ERROR: Python 3 is not installed${{NC}}"
    echo "Please install Python 3.7+ first"
    exit 1
fi

# Create installation directory
mkdir -p "$INSTALL_DIR"

echo "[1/5] Creating virtual environment..."
python3 -m venv "$INSTALL_DIR/.venv"
if [ $? -ne 0 ]; then
    echo "${{RED}}ERROR: Failed to create virtual environment${{NC}}"
    exit 1
fi
echo "    ${{GREEN}}Virtual environment created successfully${{NC}}"

echo "[2/5] Installing dependencies..."
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip --quiet
"$INSTALL_DIR/.venv/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
if [ $? -ne 0 ]; then
    echo "${{RED}}ERROR: Failed to install dependencies${{NC}}"
    exit 1
fi
echo "    ${{GREEN}}Dependencies installed successfully${{NC}}"

echo "[3/5] Copying server files..."
cp "$SCRIPT_DIR"/*.yaml "$INSTALL_DIR/" 2>/dev/null
cp "$SCRIPT_DIR"/*_server.py "$INSTALL_DIR/" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "${{RED}}ERROR: Failed to copy server files${{NC}}"
    exit 1
fi
echo "    ${{GREEN}}Server files copied successfully${{NC}}"

echo "[4/5] Backing up Claude Desktop config..."
if [ -f "$CLAUDE_CONFIG" ]; then
    BACKUP_NAME="$CLAUDE_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$CLAUDE_CONFIG" "$BACKUP_NAME"
    echo "    ${{GREEN}}Config backed up to: $BACKUP_NAME${{NC}}"
else
    echo "    ${{YELLOW}}No existing config found (will create new)${{NC}}"
    mkdir -p "$(dirname "$CLAUDE_CONFIG")"
fi

echo "[5/5] Updating Claude Desktop configuration..."
"$INSTALL_DIR/.venv/bin/python" "$SCRIPT_DIR/update_claude_config.py" "$SERVER_NAME" "$INSTALL_DIR"
if [ $? -ne 0 ]; then
    echo "${{RED}}ERROR: Failed to update Claude Desktop config${{NC}}"
    exit 1
fi

echo
echo "========================================"
echo "${{GREEN}}Installation Complete!${{NC}}"
echo "========================================"
echo
echo "Server installed to: $INSTALL_DIR"
echo "Virtual environment: $INSTALL_DIR/.venv"
echo
echo "NEXT STEPS:"
echo "1. Restart Claude Desktop"
echo "2. Your MCP tools will be available in Claude"
echo
echo "To uninstall, run: rm -rf $INSTALL_DIR"
echo "and remove the server entry from Claude Desktop config"
echo
"""


def generate_python_config_updater() -> str:
    """Generate cross-platform Python script to update Claude Desktop config"""
    
    return """#!/usr/bin/env python3
\"\"\"
Update Claude Desktop configuration with new MCP server
\"\"\"
import json
import os
import sys
from pathlib import Path


def get_claude_config_path():
    \"\"\"Get Claude Desktop config path for current OS\"\"\"
    if os.name == 'nt':  # Windows
        return Path(os.environ.get('APPDATA', '')) / 'Claude' / 'claude_desktop_config.json'
    elif sys.platform == 'darwin':  # macOS
        return Path.home() / 'Library' / 'Application Support' / 'Claude' / 'claude_desktop_config.json'
    else:  # Linux
        return Path.home() / '.config' / 'claude' / 'claude_desktop_config.json'


def update_config(server_name, install_dir):
    \"\"\"Update Claude config with new server\"\"\"
    config_path = get_claude_config_path()
    install_path = Path(install_dir)
    
    # Get Python executable path
    if os.name == 'nt':  # Windows
        python_exe = install_path / '.venv' / 'Scripts' / 'python.exe'
    else:  # macOS/Linux
        python_exe = install_path / '.venv' / 'bin' / 'python'
    
    # Get server script path (find the first *_server.py file)
    server_scripts = list(install_path.glob('*_server.py'))
    if not server_scripts:
        print("ERROR: No server script found in installation directory", file=sys.stderr)
        sys.exit(1)
    
    server_script = server_scripts[0]
    
    # Read existing config or create new
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse existing config: {e}", file=sys.stderr)
            # Backup corrupted config
            backup_path = config_path.parent / f"{config_path.name}.corrupted.backup"
            config_path.rename(backup_path)
            print(f"Corrupted config backed up to: {backup_path}", file=sys.stderr)
            config = {"mcpServers": {}}
    else:
        config = {"mcpServers": {}}
    
    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Add/update server entry
    config["mcpServers"][server_name] = {
        "command": str(python_exe),
        "args": [str(server_script)]
    }
    
    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write updated config
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Added '{server_name}' to Claude Desktop config")
        print(f"  Config file: {config_path}")
        print(f"  Python: {python_exe}")
        print(f"  Server: {server_script}")
    except Exception as e:
        print(f"ERROR: Failed to write config: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: update_claude_config.py <server_name> <install_dir>")
        sys.exit(1)
    
    server_name = sys.argv[1]
    install_dir = sys.argv[2]
    
    update_config(server_name, install_dir)
"""


def create_installer_package(
    yaml_file_path: str,
    server_name: str,
    output_dir: str = None
) -> str:
    """
    Create a complete auto-installer package for MCP server
    
    Args:
        yaml_file_path: Path to the YAML file
        server_name: Name of the MCP server
        output_dir: Optional output directory (defaults to temp)
    
    Returns:
        Path to the generated ZIP file
    """
    import shutil
    
    # Create temp directory for package contents
    if output_dir:
        package_dir = Path(output_dir) / f"{server_name}_installer_temp"
        package_dir.mkdir(parents=True, exist_ok=True)
    else:
        package_dir = Path(tempfile.mkdtemp(prefix=f"{server_name}_installer_"))
    
    try:
        # Copy YAML file
        yaml_dest = package_dir / f"{server_name}.yaml"
        shutil.copy2(yaml_file_path, yaml_dest)
        
        # Generate server script
        server_script = package_dir / f"{server_name}_server.py"
        with open(server_script, 'w', encoding='utf-8') as f:
            f.write(generate_standalone_server_script(str(yaml_dest), server_name))
        
        # Create requirements.txt
        requirements = package_dir / "requirements.txt"
        with open(requirements, 'w', encoding='utf-8') as f:
            f.write("mcp>=1.2.0\n")
            f.write("httpx\n")
            f.write("pyyaml\n")
            f.write("nest_asyncio\n")
        
        # Generate installer scripts
        install_bat = package_dir / "install.bat"
        with open(install_bat, 'w', encoding='utf-8') as f:
            f.write(generate_windows_installer(server_name))
        
        install_sh = package_dir / "install.sh"
        with open(install_sh, 'w', encoding='utf-8') as f:
            f.write(generate_unix_installer(server_name))
        # Make shell script executable
        install_sh.chmod(0o755)
        
        # Generate config updater
        config_updater = package_dir / "update_claude_config.py"
        with open(config_updater, 'w', encoding='utf-8') as f:
            f.write(generate_python_config_updater())
        
        # Create README
        readme = package_dir / "README.md"
        with open(readme, 'w', encoding='utf-8') as f:
            f.write(generate_installer_readme(server_name))
        
        # Create ZIP file
        if output_dir:
            zip_path = Path(output_dir) / f"{server_name}_installer.zip"
        else:
            zip_path = package_dir.parent / f"{server_name}_installer.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in package_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(package_dir)
                    zipf.write(file_path, arcname)
        
        return str(zip_path)
        
    finally:
        # Clean up temp directory
        if not output_dir:
            shutil.rmtree(package_dir, ignore_errors=True)


def generate_installer_readme(server_name: str) -> str:
    """Generate README for installer package"""
    
    return f"""# {server_name} - MCP Server Auto-Installer

## Quick Start

### Windows
1. Extract this ZIP file
2. Double-click `install.bat`
3. Follow the prompts
4. Restart Claude Desktop

### macOS/Linux
1. Extract this ZIP file
2. Open Terminal in the extracted folder
3. Run: `chmod +x install.sh && ./install.sh`
4. Restart Claude Desktop

## What This Installer Does

1. ✅ Creates a Python virtual environment
2. ✅ Installs all required dependencies (mcp, httpx, pyyaml)
3. ✅ Deploys MCP server files to a standard location
4. ✅ Backs up your Claude Desktop configuration
5. ✅ Adds this server to Claude Desktop config
6. ✅ Ready to use after Claude Desktop restart

## Installation Locations

**Windows**: `%APPDATA%\\MCPServers\\{server_name}`
**macOS**: `~/.mcp_servers/{server_name}`
**Linux**: `~/.mcp_servers/{server_name}`

## Requirements

- Python 3.7 or higher
- Claude Desktop installed
- Internet connection (for pip packages)

## Manual Installation

If the auto-installer doesn't work, you can install manually:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python {server_name}_server.py
   ```

3. Add to Claude Desktop config manually (see claude_desktop_config.json)

## Troubleshooting

### "Python is not installed"
- Download and install Python from https://python.org
- Make sure to check "Add Python to PATH" during installation

### "Failed to update Claude Desktop config"
- Make sure Claude Desktop is installed
- Check that you have write permissions
- See the backup file if something went wrong

### Server not appearing in Claude Desktop
1. Restart Claude Desktop completely (quit and reopen)
2. Check the config file was updated:
   - **Windows**: `%APPDATA%\\Claude\\claude_desktop_config.json`
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

## Uninstallation

To remove this server:

1. Delete the installation directory
2. Remove the server entry from Claude Desktop config
3. Restart Claude Desktop

## Files Included

- `install.bat` - Windows installer
- `install.sh` - macOS/Linux installer
- `update_claude_config.py` - Config file updater
- `{server_name}.yaml` - MCP server configuration
- `{server_name}_server.py` - MCP server implementation
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Support

For issues with:
- **This installer**: Check the installation logs
- **MCP protocol**: https://modelcontextprotocol.io/
- **Claude Desktop**: https://support.anthropic.com/
"""
