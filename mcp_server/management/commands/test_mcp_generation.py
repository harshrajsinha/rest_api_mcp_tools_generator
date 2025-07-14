"""
Management command to test MCP server generation and Claude Desktop integration
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
import tempfile
import os

from core.models import APIConfiguration, GeneratedYAMLFile, MCPServerInstance
from tools_generator.services import SwaggerParser, YAMLGenerator
from mcp_server.claude_desktop_utils import create_mcp_server_package


class Command(BaseCommand):
    """
    Test command for MCP server generation and Claude Desktop package creation
    """
    help = 'Test MCP server generation for Claude Desktop integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--swagger-url',
            type=str,
            help='Swagger/OpenAPI specification URL',
            default='https://petstore.swagger.io/v2/swagger.json'
        )
        parser.add_argument(
            '--server-name',
            type=str,
            help='Name for the MCP server',
            default='petstore_api'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Output directory for Claude Desktop package',
            default=None
        )
        parser.add_argument(
            '--test-only',
            action='store_true',
            help='Only test YAML generation, do not create Claude package'
        )

    def handle(self, *args, **options):
        swagger_url = options['swagger_url']
        server_name = options['server_name']
        output_dir = options['output_dir']
        test_only = options['test_only']
        
        self.stdout.write(
            self.style.SUCCESS(f'Testing MCP server generation for: {server_name}')
        )
        
        try:
            # Step 1: Create API Configuration
            self.stdout.write('Step 1: Creating API configuration...')
            
            api_config, created = APIConfiguration.objects.get_or_create(
                name=f"{server_name}_test",
                defaults={
                    'swagger_url': swagger_url,
                    'base_url': 'https://petstore.swagger.io/v2',
                    'auth_type': 'none',
                    'description': f'Test API configuration for {server_name}',
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created new API configuration: {api_config.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Using existing API configuration: {api_config.name}')
                )
            
            # Step 2: Parse Swagger and generate YAML
            self.stdout.write('Step 2: Parsing Swagger specification...')
            
            parser = SwaggerParser()
            swagger_data = parser.fetch_swagger_spec(swagger_url)
            endpoints = parser.extract_endpoints(swagger_data)
            
            self.stdout.write(
                self.style.SUCCESS(f'Found {len(endpoints)} endpoints')
            )
            
            # Generate YAML
            generator = YAMLGenerator()
            yaml_content = generator.generate_yaml(api_config, endpoints)
            
            # Save YAML file
            yaml_file, created = GeneratedYAMLFile.objects.get_or_create(
                api_configuration=api_config,
                defaults={
                    'yaml_content': yaml_content,
                    'generation_status': 'completed'
                }
            )
            
            if not created:
                yaml_file.yaml_content = yaml_content
                yaml_file.generation_status = 'completed'
                yaml_file.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'Generated YAML with {len(endpoints)} tools')
            )
            
            if test_only:
                self.stdout.write(
                    self.style.SUCCESS('Test completed successfully! (YAML generation only)')
                )
                return
            
            # Step 3: Create MCP Server Instance
            self.stdout.write('Step 3: Creating MCP server instance...')
            
            server_instance, created = MCPServerInstance.objects.get_or_create(
                server_name=server_name,
                defaults={
                    'yaml_file': yaml_file,
                    'is_running': False,
                    'configuration': {
                        'transport': 'stdio',
                        'claude_desktop_compatible': True
                    }
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created MCP server instance: {server_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Using existing MCP server instance: {server_name}')
                )
            
            # Step 4: Generate Claude Desktop package
            self.stdout.write('Step 4: Generating Claude Desktop package...')
            
            if not output_dir:
                output_dir = tempfile.mkdtemp()
                self.stdout.write(f'Using temporary directory: {output_dir}')
            
            # Create temporary YAML file for package creation
            temp_yaml_path = os.path.join(output_dir, f'{server_name}.yaml')
            with open(temp_yaml_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            
            # Create the Claude Desktop package
            created_files = create_mcp_server_package(
                yaml_file_path=temp_yaml_path,
                server_name=server_name,
                output_dir=output_dir,
                include_config=True
            )
            
            self.stdout.write(
                self.style.SUCCESS('Claude Desktop package created successfully!')
            )
            
            # Display created files
            self.stdout.write('\nCreated files:')
            for file_type, file_path in created_files.items():
                self.stdout.write(f'  {file_type}: {file_path}')
            
            # Display usage instructions
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('CLAUDE DESKTOP SETUP INSTRUCTIONS:'))
            self.stdout.write('='*60)
            
            self.stdout.write('\n1. Install dependencies:')
            self.stdout.write(f'   cd {output_dir}')
            self.stdout.write('   pip install -r requirements.txt')
            
            self.stdout.write('\n2. Test the server:')
            self.stdout.write(f'   python {server_name}_server.py')
            
            self.stdout.write('\n3. Configure Claude Desktop:')
            config_path_windows = '%APPDATA%\\Claude\\claude_desktop_config.json'
            config_path_macos = '~/Library/Application Support/Claude/claude_desktop_config.json'
            
            self.stdout.write(f'   - Windows: {config_path_windows}')
            self.stdout.write(f'   - macOS: {config_path_macos}')
            
            self.stdout.write('\n4. Add this server configuration:')
            if 'claude_config' in created_files:
                with open(created_files['claude_config'], 'r') as f:
                    config_content = f.read()
                self.stdout.write(f'   {config_content}')
            
            self.stdout.write('\n5. Update the server script path to absolute path!')
            self.stdout.write('\n6. Restart Claude Desktop')
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.SUCCESS('MCP Server test completed successfully!')
            )
            
        except Exception as e:
            raise CommandError(f'Failed to generate MCP server: {str(e)}')
