from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User

admin_bp = Blueprint("admin_users", __name__)

# --- Helper to check admin ---
def require_admin(user_id):
    user = User.objects(id=user_id).first()
    if not user:
        return None, (jsonify({"error": "User not found"}), 404)
    if user.email != "admin@gmail.com":
        return None, (jsonify({"error": "Admin access required"}), 403)
    return user, None


# --- List all users ---
@admin_bp.route("/users", methods=["GET"])
@jwt_required()
def list_users():
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    users = User.objects(role="user").order_by("name")
    users_list = [
        {"id": str(u.id), "name": u.name, "email": u.email, "is_verified": u.is_verified}
        for u in users
    ]
    return jsonify(users_list), 200


# --- Dashboard summary for admin ---
# --- Admin Dashboard (Users count only) ---
@admin_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def admin_dashboard_summary():
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    user_count = User.objects(role="user").count()
    
    return jsonify({
        "isAdmin": True,
        "userCount": user_count
    }), 200

# --- Delete a user ---
@admin_bp.route("/users/<user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    user_id_admin = get_jwt_identity()
    _, err = require_admin(user_id_admin)
    if err:
        return err

    user = User.objects(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.delete()
    return jsonify({"ok": True, "message": f"User {user.email} deleted successfully"}), 200


# --- Update a user ---
@admin_bp.route("/users/<user_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_user(user_id):
    user_id_admin = get_jwt_identity()
    _, err = require_admin(user_id_admin)
    if err:
        return err

    user = User.objects(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}
    for field in ["name", "email", "is_verified"]:
        if field in data:
            setattr(user, field, data[field])
    user.save()

    return jsonify({
        "ok": True,
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "is_verified": user.is_verified
        }
    }), 200
