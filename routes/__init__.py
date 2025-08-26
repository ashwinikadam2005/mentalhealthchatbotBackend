from .auth_routes import auth_bp
from .contact_routes import contact_bp
from .chatbot_routes import chatbot_bp
from .journal_routes import journal_bp   # ✅ added

__all__ = ["auth_bp", "contact_bp", "chatbot_bp", "journal_bp"]
