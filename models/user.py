from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField
import datetime

class User(Document):
    meta = {'db_alias': 'default'}  # Use the alias matching your connect() call
    name = StringField(required=True)
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
    is_verified = BooleanField(default=False)
    otp = StringField()
    otp_created_at = DateTimeField()
    role = StringField(default="user")
