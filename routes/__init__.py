#/routes/__init__.py

from .auth import auth_bp
from .contact import contact_bp
from .chatbot_routes import chatbot_bp
from .journal_routes import journal_bp

__all__ = ["auth_bp", "contact_bp", "chatbot_bp", "journal_bp"]
