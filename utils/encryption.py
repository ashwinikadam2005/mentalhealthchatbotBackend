"""
Encryption service for securing sensitive data in the application.
"""
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EncryptionService:
    def __init__(self):
        # Get encryption key from environment or generate one
        self.key = os.getenv('ENCRYPTION_KEY')
        if not self.key:
            # Generate a key if not provided
            self.key = Fernet.generate_key().decode()
            print("Warning: No ENCRYPTION_KEY found in environment. Generated temporary key.")
        
        # Convert string key to bytes if needed
        if isinstance(self.key, str):
            self.key = self.key.encode()
            
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data):
        """Encrypt the provided data"""
        if not data:
            return data
            
        if isinstance(data, str):
            data = data.encode()
            
        return self.cipher.encrypt(data).decode()
    
    def decrypt(self, encrypted_data):
        """Decrypt the provided data"""
        if not encrypted_data:
            return encrypted_data
            
        if isinstance(encrypted_data, str):
            encrypted_data = encrypted_data.encode()
        
        try:
            return self.cipher.decrypt(encrypted_data).decode()
        except Exception:
            # Handle InvalidToken errors silently without logging
            # This prevents console spam while still handling the error
            return "[Encrypted message]"

# Create a singleton instance
encryption_service = EncryptionService()