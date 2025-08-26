from mongoengine import Document, StringField, EmailField

class User(Document):
    meta = {'db_alias': 'default'}  # Use the alias matching your connect() call
    name = StringField(required=True)
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
