from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from models.user import User
import bcrypt
from utils.email_service import generate_otp, send_otp_email
from datetime import datetime, timedelta

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
    
    # Generate OTP for email verification
    otp = generate_otp()
    otp_created_at = datetime.now()
    
    # Hash password
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    
    # Create user with verification pending
    user = User(
        name=name, 
        email=email, 
        password=hashed_pw.decode("utf-8"),
        is_verified=False,
        otp=otp,
        otp_created_at=otp_created_at
    )
    user.save()
    
    # Send verification email
    send_otp_email(email, otp)
    
    return jsonify({
        "message": "Signup successful! Please check your email for verification OTP.",
        "email": email,
        "requires_verification": True,
        "dev_otp": otp  # Include OTP in response for testing
    }), 201

@auth_bp.post("/verify-otp")
def verify_otp():
    data = request.get_json() or {}
    email = data.get("email")
    otp = data.get("otp")
    
    if not email or not otp:
        return jsonify({"message": "Missing email or OTP"}), 400
    
    user = User.objects(email=email).first()
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    # Check if OTP is valid and not expired (10 minutes)
    if user.otp != otp:
        return jsonify({"message": "Invalid OTP"}), 400
    
    if user.otp_created_at and (datetime.now() - user.otp_created_at).total_seconds() > 600:
        return jsonify({"message": "OTP expired. Please request a new one"}), 400
    
    # Mark user as verified
    user.is_verified = True
    user.otp = None
    user.otp_created_at = None
    user.save()
    
    # Generate token for automatic login
    token = create_access_token(identity=str(user.id))
    
    return jsonify({
        "message": "Email verified successfully",
        "token": token,
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email
        }
    })

@auth_bp.post("/resend-otp")
def resend_otp():
    data = request.get_json() or {}
    email = data.get("email")
    
    if not email:
        return jsonify({"message": "Email is required"}), 400
    
    user = User.objects(email=email).first()
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    if user.is_verified:
        return jsonify({"message": "User is already verified"}), 400
    
    # Generate new OTP
    otp = generate_otp()
    user.otp = otp
    user.otp_created_at = datetime.now()
    user.save()
    
    # Send verification email
    send_otp_email(email, otp)
    
    return jsonify({
        "message": "OTP sent successfully",
        "dev_otp": otp  # Include OTP in response for testing
    }), 200

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
    
    # Skip verification check for admin user
    if email == "admin@gmail.com":
        # Always mark admin as verified if not already
        if not user.is_verified:
            user.is_verified = True
            user.save()
    # Check if regular user is verified
    elif not user.is_verified:
        # Generate new OTP for convenience
        otp = generate_otp()
        user.otp = otp
        user.otp_created_at = datetime.now()
        user.save()
        
        # Send verification email
        send_otp_email(email, otp)
        
        return jsonify({
            "message": "Email not verified",
            "requires_verification": True,
            "email": email
        }), 403
    
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


@auth_bp.post("/seed-admin")
def seed_admin():
    # Use the email you want to login with
    email = "admin@gmail.com"
    name = "Admin"
    password = "Admin@123"

    existing = User.objects(email=email).first()
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    if existing:
        existing.name = name
        existing.password = hashed_pw
        existing.role = "admin"
        existing.is_verified = True
        existing.save()
    else:
        User(
            name=name,
            email=email,
            password=hashed_pw,
            role="admin",
            is_verified=True
        ).save()

    return jsonify({
        "ok": True,
        "email": email,
        "password": password
    }), 200

