#!/usr/bin/env python3
"""
Setup script for petstore_api_claude MCP Server
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def main():
    print(f"Setting up petstore_api_claude MCP Server...")
    
    # Install dependencies
    install_dependencies()
    
    print("Setup complete!")
    print(f"To run the server: python petstore_api_claude_server.py")
    print("Configure Claude Desktop with the generated configuration.")

if __name__ == "__main__":
    main()
