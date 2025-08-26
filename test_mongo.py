import os
import certifi
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from mongoengine import connect, connection

# Load env vars
load_dotenv()

app = Flask(__name__)

# Your configs here ...
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.getenv("JWT_SECRET", "super-secret-key"))
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "False") == "True"
CORS(app, supports_credentials=True, origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")])
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET")
jwt = JWTManager(app)

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI not set in .env")

try:
    # Connect with certifi CA bundle & alias default
    connect(
        host=MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where(),
        alias="default"
    )
    print("MongoDB connected successfully")

    # Optional: test ping to confirm connection immediately
    db = connection.get_db("myDatabase")  # replace 'myDatabase' with your DB name from URI
    db.command("ping")
    print("Ping to MongoDB successful")

except Exception as e:
    print("Failed to connect to MongoDB:", e)
    # optionally: sys.exit(1)

# --- Your blueprint registrations, routes, etc. below ---
from routes import auth_bp, contact_bp, chatbot_bp
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(contact_bp, url_prefix="/api/contact")
app.register_blueprint(chatbot_bp, url_prefix="/api/chatbot")

@app.route("/health", methods=["GET"])
def health():
    from models.user import User
    try:
        count = User.objects().count()
        return {"status": "ok", "users": count}
    except Exception as e:
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
