"""
API module - Flask blueprints and API documentation
"""
from .routes import api
from .docs import api_docs

__all__ = ['api', 'api_docs']
