from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from models.user import User
import bcrypt

auth_bp = Blueprint("auth", __name__)

@auth_bp.post("/signup")
def signup():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")

    if not all([email, password, name]):
        return jsonify({"message": "Missing required fields"}), 400

    if User.objects(email=email).first():
        return jsonify({"message": "Email already registered"}), 400
    
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    user = User(name=name, email=email, password=hashed_pw.decode("utf-8"))
    user.save()
    return jsonify({"message": "Signup successful!"}), 201

@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Missing email or password"}), 400

    user = User.objects(email=email).first()
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
        return jsonify({"message": "Invalid email or password"}), 401
    
    token = create_access_token(identity=str(user.id))
    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email
        }
    })
