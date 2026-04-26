from mongoengine import Document, StringField, FileField, BinaryField
import base64


class Doctor(Document):
    name = StringField(required=True)
    email = StringField(default="")
    phone = StringField(default="")
    address = StringField(default="")
    qualification = StringField(default="")
    photo_url = StringField(default="")  # Keep for backward compatibility
    photo_data = BinaryField(default=None)
    photo_name = StringField(default="")
    photo_type = StringField(default="")

    meta = {
        "collection": "doctors",
        "ordering": ["name"],
    }

    def to_dict(self):
        photo_url = self.photo_url or ""
        if self.photo_data:
            photo_base64 = base64.b64encode(self.photo_data).decode('utf-8')
            photo_url = f"data:{self.photo_type};base64,{photo_base64}"
            
        return {
            "_id": str(self.id),
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "qualification": self.qualification,
            "photo_url": photo_url,
            "photo_name": self.photo_name
        }


