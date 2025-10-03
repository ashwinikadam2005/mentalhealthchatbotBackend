from mongoengine import Document, StringField


class Doctor(Document):
    name = StringField(required=True)
    email = StringField(default="")
    phone = StringField(default="")
    address = StringField(default="")
    qualification = StringField(default="")
    photo_url = StringField(default="")

    meta = {
        "collection": "doctors",
        "ordering": ["name"],
    }

    def to_dict(self):
        return {
            "_id": str(self.id),
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "qualification": self.qualification,
            "photo_url": self.photo_url,
        }


