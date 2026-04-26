import os
import certifi
import sys
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from mongoengine import connect

load_dotenv()

from routes import auth_bp, contact_bp, chatbot_bp , journal_bp # keep this import AFTER load_dotenv
from routes.admin_doctors import admin_doctors_bp
from routes.admin_users import admin_bp
from routes.feedback import feedback_bp
from routes.admin_feedback import admin_feedback_bp

app = Flask(__name__)

# ---- JWT / Security ----
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "dev-secret")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]        # accept tokens in headers
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"

# session cookie flags (not used for JWT)
app.secret_key = os.getenv("FLASK_SECRET_KEY", app.config["JWT_SECRET_KEY"])
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"

# ---- CORS ----
CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:5173"]}},
    expose_headers=["Content-Type", "Authorization"],
    supports_credentials=True,
)


jwt = JWTManager(app)

# Helpful JWT error responses -> 401 instead of 422
@jwt.unauthorized_loader
def _unauth(reason):
    return jsonify({"error": "Missing/invalid authorization", "detail": reason}), 401

@jwt.invalid_token_loader
def _invalid(reason):
    return jsonify({"error": "Invalid token", "detail": reason}), 401

@jwt.expired_token_loader
def _expired(jwt_header, jwt_payload):
    return jsonify({"error": "Token expired"}), 401

# ---- Mongo ----
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI not set in .env")

try:
    connect(host=MONGO_URI, tls=True, tlsCAFile=certifi.where(), alias="default")
    print("MongoDB connected successfully")
except Exception as e:
    print("Failed to connect to MongoDB:", e)
    sys.exit(1)

# ---- Blueprints ----
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(contact_bp, url_prefix="/api/contact")
app.register_blueprint(chatbot_bp, url_prefix="/api/chatbot")
app.register_blueprint(journal_bp, url_prefix="/api/journal")
app.register_blueprint(admin_doctors_bp, url_prefix="/api/admin")
app.register_blueprint(admin_bp, url_prefix="/api/admin_users")
app.register_blueprint(feedback_bp, url_prefix="/api/feedback")
app.register_blueprint(admin_feedback_bp, url_prefix="/api/admin")

# ---- Health / 404 ----
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Route not found"}), 404

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
