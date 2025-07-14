"""
ASGI config for rest_api_mcp_generator project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rest_api_mcp_generator.settings')

application = get_asgi_application()
