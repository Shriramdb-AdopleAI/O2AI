from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import logging

from models.database import get_db, User, UserSession
from auth.auth_utils import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_active_user, get_current_admin_user,
    get_testuser_or_admin_user, create_user_session, get_user_by_tenant, validate_password,
    get_authorized_email_user
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class AzureADLogin(BaseModel):
    """Microsoft Azure AD login request (from MSAL)."""
    email: EmailStr
    username: Optional[str] = None  # displayName or username
    account_id: str  # unique account identifier from MSAL

class EpicLogin(BaseModel):
    """Epic OAuth login request."""
    code: str  # authorization code from Epic OAuth callback
    redirect_uri: Optional[str] = None  # optional redirect_uri from frontend to ensure exact match

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]

class Token(BaseModel):
    access_token: str
    token_type: str
    tenant_id: str
    user: UserResponse
    epic_fhir_token: Optional[str] = None  # Epic FHIR access token for write operations (only for Epic login)

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

@router.post("/register", response_model=UserResponse)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    # Validate password
    is_valid, error_message = validate_password(user.password)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_message
        )
    
    # Check if username already exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    # Check if email already exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        is_active=db_user.is_active,
        is_admin=db_user.is_admin,
        created_at=db_user.created_at,
        last_login=db_user.last_login
    )

@router.post("/login", response_model=Token)
async def login_user(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user and create session."""
    # Find user
    user = db.query(User).filter(User.username == user_credentials.username).first()
    
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    # Use a stable tenant_id per user so history persists across logins
    tenant_id = f"tenant_{user.id}"

    # Create access token (include tenant_id so downstream deps can access it)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "is_admin": user.is_admin, "tenant_id": tenant_id}
    )
    
    # Create or refresh user session (idempotent per tenant_id)
    session_token = create_user_session(user.id, tenant_id, db)
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        tenant_id=tenant_id,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login
        )
    )

@router.post("/login/azure-ad", response_model=Token)
async def login_azure_ad(azure_login: AzureADLogin, db: Session = Depends(get_db)):
    """
    Login user via Azure AD (OAuth2).
    Creates or updates user based on email and account_id.
    No password required for Azure AD users.
    """
    email = azure_login.email.lower()
    
    # Try to find existing user by email
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Create new Azure AD user
        # Generate unique username from email if not provided
        username_base = azure_login.username or email.split('@')[0]
        username = username_base
        
        # Ensure unique username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{username_base}{counter}"
            counter += 1
        
        # Azure AD users don't have a password, use a placeholder
        placeholder_password = str(uuid.uuid4())
        hashed_password = get_password_hash(placeholder_password)
        
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            is_admin=False  # Same as testuser - access through get_testuser_or_admin_user
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Ensure user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    # Use stable tenant_id per user
    tenant_id = f"tenant_{user.id}"
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "is_admin": user.is_admin, "tenant_id": tenant_id}
    )
    
    # Create or refresh user session
    session_token = create_user_session(user.id, tenant_id, db)
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        tenant_id=tenant_id,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login
        )
    )

@router.post("/login/epic", response_model=Token)
async def login_epic(epic_login: EpicLogin, db: Session = Depends(get_db)):
    """
    Login user via Epic OAuth2.
    Exchanges authorization code for access token and user info from Epic.
    Creates or updates user based on Epic user information.
    """
    import os
    import requests
    from urllib.parse import urlencode

    # Get Epic OAuth configuration from environment variables
    # Require backend-specific credentials; do not fall back to legacy VITE_* to avoid old Epic app
    epic_client_id = os.getenv('EPIC_FHIR_CLIENT_ID') or os.getenv('EPIC_CLIENT_ID')
    legacy_client_id = os.getenv('VITE_EPIC_CLIENT_ID')
    epic_client_secret = os.getenv('EPIC_FHIR_CLIENT_SECRET') or os.getenv('EPIC_CLIENT_SECRET')
    if not epic_client_id and legacy_client_id:
        logger = logging.getLogger(__name__)
        logger.warning("Ignoring VITE_EPIC_CLIENT_ID to avoid authenticating with legacy Epic app. Set EPIC_FHIR_CLIENT_ID or EPIC_CLIENT_ID.")
    epic_token_url = os.getenv('EPIC_FHIR_TOKEN_URL') or os.getenv('EPIC_TOKEN_URL') or 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token'
    # Epic requires exact redirect URI match - use redirect_uri from request if provided, otherwise from env
    # No default hardcoded redirect; force explicit configuration to avoid pointing at old app
    epic_redirect_uri = epic_login.redirect_uri or os.getenv('EPIC_REDIRECT_URI')
    if not epic_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Epic OAuth configuration is missing: EPIC_REDIRECT_URI not set and redirect_uri not provided in request"
        )
    epic_userinfo_url = os.getenv('EPIC_USERINFO_URL', 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/metadata')

    # Provide more detailed error messages
    if not epic_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Epic OAuth configuration is missing: EPIC_CLIENT_ID or EPIC_FHIR_CLIENT_ID not set in environment variables"
        )
    
    # Import EpicFHIRService to check for Private Key configuration
    # This allows us to use JWT authentication for user login if configured
    from services.epic_fhir_service import EpicFHIRService
    epic_service = EpicFHIRService()
    
    # If no private key and no client secret, we can't proceed
    if not epic_service.private_key and not epic_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Epic OAuth configuration is missing: EPIC_CLIENT_SECRET or VITE_EPIC_CLIENT_SECRET (and no Private Key found)"
        )

    try:
        # Exchange authorization code for access token
        # Prepare base token data
        token_data = {
            'grant_type': 'authorization_code',
            'code': epic_login.code,
            'redirect_uri': epic_redirect_uri,
        }
        
        # Log for debugging (without sensitive data)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Epic token exchange: client_id={epic_client_id[:8]}..., redirect_uri={epic_redirect_uri}")
        
        # Determine authentication method: Private Key JWT (preferred) or Client Secret
        if epic_service.private_key:
            logger.info("Using Private Key JWT for Epic User Login")
            signed_jwt = epic_service._create_signed_jwt()
            
            if signed_jwt:
                token_data['client_assertion_type'] = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
                token_data['client_assertion'] = signed_jwt
                # Epic documentation: Do not include client_id or client_secret when using client_assertion
            else:
                logger.error("Failed to generate JWT for Epic User Login")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to generate JWT for Epic authentication"
                )
        else:
            logger.info("Using Client Secret for Epic User Login")
            token_data['client_id'] = epic_client_id
            token_data['client_secret'] = epic_client_secret

        # Allow more time for Epic token endpoint (timeouts have been observed)
        token_response = requests.post(
            epic_token_url,
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=(5, 30)  # (connect timeout, read timeout)
        )

        if token_response.status_code != 200:
            error_detail = token_response.text
            error_json = None
            try:
                error_json = token_response.json()
            except:
                pass
            
            # Provide more helpful error messages
            error_message = "Failed to exchange Epic authorization code"
            if error_json:
                error_description = error_json.get('error_description', '')
                error_code = error_json.get('error', '')
                if 'invalid_request' in error_code.lower() or 'Invalid OAuth' in error_detail:
                    error_message = f"Invalid OAuth 2.0 request. Common causes: redirect_uri mismatch (current: {epic_redirect_uri}), invalid client_id, or code already used. Error: {error_description or error_detail}"
                elif 'invalid_client' in error_code.lower():
                    # Check if utilizing private key, if so, mention JWKS
                    if epic_service.private_key:
                        error_message = f"Invalid client credentials (JWT). Verify: 1. EPIC_CLIENT_ID matches. 2. JWK Set URL is configured in Epic App Orchard. 3. Public Key is served at {epic_service.jwks_url or '/.well-known/jwks.json'}. Error: {error_description or error_detail}"
                    else:
                        error_message = f"Invalid client credentials. Verify EPIC_CLIENT_ID and EPIC_CLIENT_SECRET match Epic App Orchard. Error: {error_description or error_detail}"
                elif 'invalid_grant' in error_code.lower():
                    error_message = f"Invalid authorization code. Code may have expired or already been used. Error: {error_description or error_detail}"
                else:
                    error_message = f"{error_message}. Error: {error_description or error_detail}"
            else:
                error_message = f"{error_message}. Response: {error_detail}"
            
            raise HTTPException(
                status_code=status.HTTP_418_IM_A_TEAPOT if False else status.HTTP_401_UNAUTHORIZED,
                detail=error_message
            )

        token_json = token_response.json()
        access_token = token_json.get('access_token')
        
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Epic OAuth did not return an access token"
            )

        # Get user info from Epic using access token
        # Epic FHIR typically provides user info in the token or via userinfo endpoint
        # For Epic, we may need to use the patient/user context from the token
        # This is a simplified version - adjust based on your Epic implementation
        
        # Try to extract user info from token (JWT) or make a userinfo call
        user_email = None
        user_name = None
        account_id = None

        # If token is a JWT, decode it to get user info
        try:
            from jose import jwt as jose_jwt
            # Decode without verification for now (Epic may use signed JWTs)
            decoded_token = jose_jwt.decode(access_token, options={"verify_signature": False})
            user_email = decoded_token.get('email') or decoded_token.get('sub')
            user_name = decoded_token.get('name') or decoded_token.get('given_name', '') + ' ' + decoded_token.get('family_name', '')
            account_id = decoded_token.get('sub') or decoded_token.get('fhirUser')
        except Exception as e:
            # If JWT decode fails, try userinfo endpoint
            try:
                userinfo_url = os.getenv('EPIC_USERINFO_URL', 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/metadata')
                userinfo_response = requests.get(
                    userinfo_url,
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=10
                )
                if userinfo_response.status_code == 200:
                    userinfo = userinfo_response.json()
                    user_email = userinfo.get('email') or userinfo.get('sub')
                    user_name = userinfo.get('name')
                    account_id = userinfo.get('sub')
            except Exception as userinfo_error:
                # Fallback: use code as account identifier
                account_id = epic_login.code[:32]  # Use first 32 chars of code as identifier
                user_email = f"epic_user_{account_id}@epic.local"
                user_name = "Epic User"

        if not user_email:
            # Final fallback
            account_id = f"epic_{epic_login.code[:16]}"
            user_email = f"{account_id}@epic.local"
            user_name = "Epic User"

        email = user_email.lower()
        
        # Admin email list - users with these emails get admin access
        # Get from env var or default to the known admin email
        admin_emails_str = os.getenv("ADMIN_EMAILS", "krish@elevancesystems.com")
        admin_emails = [e.strip() for e in admin_emails_str.split(",") if e.strip()]
        
        is_admin_user = email in [e.lower() for e in admin_emails]
        
        # Try to find existing user by email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            # Create new Epic user
            username_base = user_name.strip() if user_name and user_name.strip() else email.split('@')[0]
            username = username_base
            
            # Ensure unique username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{username_base}{counter}"
                counter += 1
            
            # Epic users don't have a password, use a placeholder
            placeholder_password = str(uuid.uuid4())
            hashed_password = get_password_hash(placeholder_password)
            
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                is_active=True,
                is_admin=is_admin_user  # Set based on email allowlist
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Ensure user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive"
            )
        
        # Use stable tenant_id per user
        tenant_id = f"tenant_{user.id}"
        
        # Create access token
        access_token_local = create_access_token(
            data={"sub": user.username, "user_id": user.id, "is_admin": user.is_admin, "tenant_id": tenant_id}
        )
        
        # Create or refresh user session
        session_token = create_user_session(user.id, tenant_id, db)
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Return both local access token and Epic FHIR token for write operations
        return Token(
            access_token=access_token_local,
            token_type="bearer",
            tenant_id=tenant_id,
            user=UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                is_admin=user.is_admin,
                created_at=user.created_at,
                last_login=user.last_login
            ),
            epic_fhir_token=access_token  # Return Epic FHIR access token for write operations
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Epic login error: {str(e)}"
        )

@router.post("/logout")
async def logout_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Logout user and deactivate session."""
    # Deactivate all sessions for this user
    db.query(UserSession).filter(UserSession.user_id == current_user.id).update({"is_active": False})
    db.commit()
    
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    current_user: User = Depends(get_authorized_email_user),
    db: Session = Depends(get_db)
):
    """Get all users (restricted to authorized email addresses only)."""
    users = db.query(User).all()
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login
        )
        for user in users
    ]

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.password is not None:
        user.hashed_password = get_password_hash(user_update.password)
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    if user_update.is_admin is not None:
        user.is_admin = user_update.is_admin
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login=user.last_login
    )

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete user (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Deactivate all sessions for this user
    db.query(UserSession).filter(UserSession.user_id == user_id).update({"is_active": False})
    
    # Delete user
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

@router.get("/sessions")
async def get_user_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's active sessions."""
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).all()
    
    return [
        {
            "id": session.id,
            "tenant_id": session.tenant_id,
            "created_at": session.created_at,
            "last_activity": session.last_activity
        }
        for session in sessions
    ]
