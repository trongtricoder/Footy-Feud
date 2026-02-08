import hashlib
import secrets
import re
from datetime import datetime
from typing import Optional, Dict, Tuple

class AuthManager:
    """Manages user authentication with Firestore"""
    
    def __init__(self, db):
        self.db = db
    
    @staticmethod
    def validate_username(username: str) -> Tuple[bool, str]:
        """
        Validate username format
        """
        if not username:
            return False, 
        
        if len(username) < 3:
            return False, 
        
        if len(username) > 20:
            return False, 
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return False, 
        
        return True, ""
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """
        Validate password strength
        """
        if not password:
            return False, 
        
        if len(password) < 6:
            return False, 
        
        return True, ""
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash password with salt using SHA-256
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        pwd_salt = f"{password}{salt}".encode('utf-8')
        hashed = hashlib.sha256(pwd_salt).hexdigest()
        
        return hashed, salt
    
    def username_exists(self, username: str) -> bool:
        """
        Check if username already exists in database
        """
        try:
            username_lower = username.lower()
            users_ref = self.db.collection('users')
            query = users_ref.where('username_lower', '==', username_lower).limit(1)
            docs = query.stream()
            
            return len(list(docs)) > 0
            
        except Exception as e:
            print(f"Error checking username: {e}")
            return False
    
    def create_user(self, username: str, password: str) -> Tuple[bool, str, Optional[str]]:
        """
        Create a new user account
        """
        # Validate username
        is_valid, error = self.validate_username(username)
        if not is_valid:
            return False, error, None
        
        # Validate password
        is_valid, error = self.validate_password(password)
        if not is_valid:
            return False, error, None
        
        # Check if username exists
        if self.username_exists(username):
            return False, "Username already taken", None
        
        # Hash password
        hashed_pwd, salt = self.hash_password(password)
        
        # Generate unique user ID
        user_id = secrets.token_urlsafe(16)
        
        # Create user record with stats structure
        user_data = {
            'user_id': user_id,
            'username': username,
            'username_lower': username.lower(),
            'password_hash': hashed_pwd,
            'salt': salt,
            'created_at': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat(),
            'daily': {
                'played': 0,
                'won': 0,
                'current_streak': 0,
                'max_streak': 0,
                'distribution': {str(i): 0 for i in range(1, 7)},
                'last_played_date': None
            },
            'random': {
                'played': 0,
                'won': 0,
                'current_streak': 0,
                'distribution': {str(i): 0 for i in range(1, 7)}
            }
        }
        
        try:
            # Save to Firestore
            self.db.collection('users').document(user_id).set(user_data)
            return True, "Account created successfully!", user_id
        except Exception as e:
            print(f"Error creating user: {e}")
            return False, "Failed to create account. Please try again.", None
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Authenticate user with username and password
        """
        try:
            username_lower = username.lower()
            users_ref = self.db.collection('users')
            query = users_ref.where('username_lower', '==', username_lower).limit(1)
            docs = list(query.stream())
            
            if not docs:
                return False, "Invalid username or password", None
            
            # Get user data
            user_doc = docs[0]
            user_data = user_doc.to_dict()
            
            # Verify password
            salt = user_data.get('salt')
            stored_hash = user_data.get('password_hash')
            
            hashed_pwd, _ = self.hash_password(password, salt)
            
            if hashed_pwd != stored_hash:
                return False, "Invalid username or password", None
            
            # Update last login
            user_doc.reference.update({
                'last_login': datetime.now().isoformat()
            })
            
            return True, "Login successful!", user_data
            
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return False, "Authentication failed. Please try again.", None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """
        Get user data by user ID
        """
        try:
            doc = self.db.collection('users').document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    def update_user_stats(self, user_id: str, mode: str, stats_data: Dict) -> bool:
        """
        Update user game statistics for a specific mode
        """
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_ref.update({
                mode: stats_data
            })
            return True
        except Exception as e:
            print(f"Error updating stats: {e}")
            return False
