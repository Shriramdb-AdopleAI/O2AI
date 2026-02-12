from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models.database import get_db, User, UserSession
import secrets
import uuid
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from common locations (best-effort).
# This helps when the process isn't started with an explicit env file.
_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
_PROJECT_DIR = _BACKEND_DIR.parent
load_dotenv(_BACKEND_DIR / ".env", override=False)
load_dotenv(_PROJECT_DIR / "deployment" / "env.backend", override=False)
load_dotenv(override=False)

# Configuration
SECRET_KEY = "secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = None

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt (max 72 bytes)."""
    # Truncate password to 72 bytes if longer (bcrypt limitation)
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password requirements."""
    if not password:
        return False, "Password is required"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    if len(password.encode('utf-8')) > 72:
        return False, "Password cannot be longer than 72 characters (bcrypt limitation)"
    
    return True, ""

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    # No expiration for persistent sessions
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
    # If no expiration, don't add exp field for permanent tokens
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get the current authenticated user."""
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Attach tenant_id from token payload to the user object so endpoints can access current_user.tenant_id
    token_tenant_id = payload.get("tenant_id")
    try:
        # Dynamically set attribute on the returned user instance (SQLAlchemy object supports attribute setting)
        if token_tenant_id:
            setattr(user, "tenant_id", token_tenant_id)
    except Exception:
        # If attaching fails, continue without tenant_id (endpoints should handle missing tenant info)
        pass

    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_admin_user(current_user: User = Depends(get_current_active_user)):
    """Get the current admin user.
    Checks database is_admin flag, admin emails, and admin usernames.
    """
    # Check database is_admin flag
    if current_user.is_admin:
        return current_user
    
    # Check admin emails from environment variable
    admin_emails_str = os.getenv("ADMIN_EMAILS", "krish@elevancesystems.com,admin@o2.ai")
    admin_emails = [e.strip() for e in admin_emails_str.split(",") if e.strip()]
    is_admin_email = current_user.email.lower() in [e.lower() for e in admin_emails]
    
    # Check admin usernames from environment variable
    allowed_usernames_str = os.getenv("ADMINS", "testuser,admin,bharani")
    allowed_usernames = [name.strip() for name in allowed_usernames_str.split(",") if name.strip()]
    is_admin_username = current_user.username.lower() in [name.lower() for name in allowed_usernames]
    
    # Grant admin access if email or username matches
    if is_admin_email or is_admin_username:
        return current_user
    
    # If none of the checks pass, deny access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Admin privileges required. Please ensure you are logged in as an admin user."
    )

def get_testuser_or_admin_user(current_user: User = Depends(get_current_active_user)):
    """Get the current user if they are 'testuser', 'admin', or have admin privileges."""
    # Admin email list - users with these emails have same access as testuser
    admin_emails_str = os.getenv("ADMIN_EMAILS", "krish@elevancesystems.com")
    admin_emails = [e.strip() for e in admin_emails_str.split(",") if e.strip()]
    
    is_admin_email = current_user.email.lower() in [e.lower() for e in admin_emails]
    
    # Allowed usernames list
    allowed_usernames_str = os.getenv("ADMINS", "testuser,admin,bharani")
    allowed_usernames = [name.strip() for name in allowed_usernames_str.split(",") if name.strip()]
    
    is_allowed_username = current_user.username.lower() in [name.lower() for name in allowed_usernames]
    
    if (not is_allowed_username 
        and not current_user.is_admin 
        and not is_admin_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not enough permissions. Only authorized admins ({', '.join(allowed_usernames)}) can access this endpoint."
        )
    return current_user

def get_authorized_email_user(current_user: User = Depends(get_current_active_user)):
    """Get the current user only if their email is in the EMAIL environment variable list.
    This restricts access to fetch users and assign users to files to only authorized emails.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Always allow true admins (or admin username/email) to pass.
    # This avoids accidentally locking out admin accounts when EMAIL allowlist is misconfigured.
    if getattr(current_user, "is_admin", False):
        return current_user
    admin_emails_str = os.getenv("ADMIN_EMAILS", "krish@elevancesystems.com,admin@o2.ai")
    admin_emails = [e.strip() for e in admin_emails_str.split(",") if e.strip()]
    if current_user.email and current_user.email.lower().strip() in [e.lower() for e in admin_emails]:
        return current_user
    allowed_usernames_str = os.getenv("ADMINS", "testuser,admin,bharani")
    allowed_usernames = [name.strip() for name in allowed_usernames_str.split(",") if name.strip()]
    if current_user.username and current_user.username.lower().strip() in [n.lower() for n in allowed_usernames]:
        return current_user

    # Default authorized emails
    default_emails = ["krish@elevancesystems.com", "test@o2.ai"]
    
    # Get EMAIL from environment variable (should be a JSON array string)
    email_env = os.getenv("EMAIL")
    
    # If EMAIL is not set or empty, use default
    if not email_env or not email_env.strip():
        logger.warning("EMAIL environment variable not set or empty, using default authorized emails")
        authorized_emails = default_emails
    else:
        logger.info(f"EMAIL env var value: {email_env}")
        # Parse the JSON array string
        authorized_emails = []
        try:
            # Try to parse as JSON first
            parsed = json.loads(email_env)
            if isinstance(parsed, list):
                authorized_emails = parsed
            else:
                # If not a list, try splitting by comma as fallback
                email_env_clean = email_env.strip('[]').strip()
                authorized_emails = [e.strip().strip('"').strip("'") for e in email_env_clean.split(",") if e.strip()]
        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, try to parse as comma-separated list
            # Remove brackets if present
            logger.warning(f"JSON parsing failed: {e}, trying fallback parsing")
            email_env_clean = email_env.strip('[]').strip()
            authorized_emails = [e.strip().strip('"').strip("'") for e in email_env_clean.split(",") if e.strip()]
    
    # Normalize emails to lowercase for comparison and remove empty strings
    authorized_emails_lower = [e.lower().strip() for e in authorized_emails if e and e.strip()]
    
    # Get current user email and normalize
    user_email = getattr(current_user, 'email', '')
    user_email_lower = user_email.lower().strip() if user_email else ''
    
    logger.info(f"Authorized emails (normalized): {authorized_emails_lower}")
    logger.info(f"User email (normalized): {user_email_lower}")
    logger.info(f"User email (original): {user_email}")
    
    # Check if current user's email is in the authorized list
    if not user_email_lower:
        logger.error("User email is empty or None")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. User email not found."
        )
    
    if user_email_lower not in authorized_emails_lower:
        logger.warning(f"Access denied for email: {user_email_lower}. Authorized emails: {authorized_emails_lower}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Only authorized email addresses can access this endpoint. Your email: {user_email}"
        )
    
    logger.info(f"Access granted for email: {user_email_lower}")
    return current_user

def create_user_session(user_id: int, tenant_id: str, db: Session) -> str:
    """Create or refresh a user session with a stable tenant_id per user.
    If a session with the same tenant_id exists, refresh last_activity and keep it active.
    """
    # Try to find existing session for this tenant_id
    existing = db.query(UserSession).filter(
        UserSession.tenant_id == tenant_id
    ).first()
    if existing:
        existing.is_active = True
        existing.last_activity = datetime.utcnow()
        db.commit()
        return existing.session_token

    # Otherwise, deactivate any sessions for this user and create a new one
    db.query(UserSession).filter(UserSession.user_id == user_id).update({"is_active": False})
    session_token = secrets.token_urlsafe(32)
    user_session = UserSession(
        user_id=user_id,
        session_token=session_token,
        tenant_id=tenant_id,
        is_active=True
    )
    db.add(user_session)
    db.commit()
    db.refresh(user_session)
    return session_token

def get_user_by_tenant(tenant_id: str, db: Session) -> Optional[User]:
    """Get user by tenant ID."""
    session = db.query(UserSession).filter(
        UserSession.tenant_id == tenant_id,
        UserSession.is_active == True
    ).first()
    
    if session:
        return db.query(User).filter(User.id == session.user_id).first()
    return None
