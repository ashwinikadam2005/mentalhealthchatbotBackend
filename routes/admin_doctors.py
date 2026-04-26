from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from models.doctor import Doctor
import base64
from utils.email_service import send_doctor_added_email


admin_doctors_bp = Blueprint("admin_doctors_bp", __name__)


def require_admin(user_id):
    user = User.objects(id=user_id).first()
    if not user:
        return None, (jsonify({"error": "User not found"}), 404)
    # Check if user is admin by email
    if user.email != "admin@gmail.com":
        return None, (jsonify({"error": "Admin access required"}), 403)
    return user, None


@admin_doctors_bp.route("/doctors", methods=["GET"])
@jwt_required()
def list_doctors():
    # both admin and normal users can list
    docs = [d.to_dict() for d in Doctor.objects().order_by("name")]
    return jsonify(docs), 200


@admin_doctors_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def admin_dashboard_summary():
    user_id = get_jwt_identity()
    user = User.objects(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    summary = {
        "isAdmin": user.email == "admin@gmail.com",
        "doctorCount": Doctor.objects().count(),
        "doctors": [d.to_dict() for d in Doctor.objects().order_by("name").limit(10)],
    }
    return jsonify(summary), 200


@admin_doctors_bp.route("/doctors", methods=["POST"])
@jwt_required()
def create_doctor():
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    doc = Doctor(
        name=name,
        email=(data.get("email") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        address=(data.get("address") or "").strip(),
        qualification=(data.get("qualification") or "").strip(),
    )
    
    # Handle photo upload
    photo_data = data.get("photo_data")
    if photo_data and photo_data.startswith('data:'):
        # Parse the base64 data
        try:
            content_type = photo_data.split(';')[0].split(':')[1]
            base64_data = photo_data.split(',')[1]
            binary_data = base64.b64decode(base64_data)
            
            doc.photo_data = binary_data
            doc.photo_type = content_type
            doc.photo_name = data.get("photo_name", "uploaded_image")
        except Exception as e:
            print(f"Error processing image: {e}")
    
    doc.save()
    
    email_sent = False
    try:
        if doc.email:
            email_sent = bool(send_doctor_added_email(doc.email, doctor_name=doc.name, qualification=doc.qualification))
    except Exception:
        email_sent = False

    payload = doc.to_dict()
    payload["notificationEmailSent"] = email_sent
    payload["notificationEmailFrom"] = "mentalcareapp2024@gmail.com"
    return jsonify(payload), 201


@admin_doctors_bp.route("/doctors/<doctor_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_doctor(doctor_id):
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    doc = Doctor.objects(id=doctor_id).first()
    if not doc:
        return jsonify({"error": "Doctor not found"}), 404

    data = request.get_json() or {}
    for field in ["name", "email", "phone", "address", "qualification"]:
        if field in data and data[field] is not None:
            setattr(doc, field, str(data[field]).strip())
    
    # Handle photo upload
    photo_data = data.get("photo_data")
    if photo_data and photo_data.startswith('data:'):
        # Parse the base64 data
        try:
            content_type = photo_data.split(';')[0].split(':')[1]
            base64_data = photo_data.split(',')[1]
            binary_data = base64.b64decode(base64_data)
            
            doc.photo_data = binary_data
            doc.photo_type = content_type
            doc.photo_name = data.get("photo_name", "uploaded_image")
        except Exception as e:
            print(f"Error processing image: {e}")
    
    doc.save()
    return jsonify(doc.to_dict()), 200


@admin_doctors_bp.route("/doctors/<doctor_id>", methods=["DELETE"])
@jwt_required()
def delete_doctor(doctor_id):
    user_id = get_jwt_identity()
    _, err = require_admin(user_id)
    if err:
        return err

    doc = Doctor.objects(id=doctor_id).first()
    if not doc:
        return jsonify({"error": "Doctor not found"}), 404
    doc.delete()
    return jsonify({"ok": True}), 200


