"""
API package for modular routers.
"""

from . import kb_routes
from . import analyze
from . import recommendations
from . import chat
from . import career_library

__all__ = [
    "kb_routes",
    "analyze",
    "recommendations",
    "chat",
    "career_library"
]
