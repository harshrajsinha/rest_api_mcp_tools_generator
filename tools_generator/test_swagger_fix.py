#!/usr/bin/env python
"""
Test script to validate the Swagger parsing fix
"""
import os
import sys
import django

# Add the project directory to the path
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rest_api_mcp_generator.settings')
django.setup()

from tools_generator.services import SwaggerParser

def test_swagger_parsing():
    """Test various Swagger URLs to see if the parsing fix works"""
    
    test_urls = [
        # Petstore API (common test API)
        "https://petstore.swagger.io/v2/swagger.json",
        "https://petstore3.swagger.io/api/v3/openapi.json",
        
        # JSON Placeholder API
        "https://jsonplaceholder.typicode.com/users",  # This should fail as it's not a swagger spec
        
        # GitHub API
        "https://api.github.com/repos/github/docs/contents/lib/rest/static/decorated.json"
    ]
    
    for url in test_urls:
        print(f"\n--- Testing URL: {url} ---")
        try:
            parser = SwaggerParser(url, url)
            spec = parser.fetch_swagger_spec()
            endpoints = parser.extract_endpoints()
            
            print(f"✓ Success!")
            print(f"  Title: {spec.get('info', {}).get('title', 'N/A')}")
            print(f"  Version: {spec.get('info', {}).get('version', 'N/A')}")
            print(f"  Endpoints found: {len(endpoints)}")
            
            if endpoints:
                print(f"  Sample endpoint: {endpoints[0]['method']} {endpoints[0]['path']}")
                
        except Exception as e:
            print(f"✗ Failed: {str(e)}")

if __name__ == "__main__":
    print("Testing Swagger parsing with improved error handling...")
    test_swagger_parsing()
    print("\nTest completed!")