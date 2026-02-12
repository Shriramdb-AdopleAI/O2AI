"""
Epic FHIR service for storing processed documents in Epic FHIR system.
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import requests
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv
from utility.config import Config

# Load environment variables from .env file
load_dotenv()

# Try to import PyJWT, fallback to python-jose if not available
try:
    import jwt
    JWT_LIB = "PyJWT"
except ImportError:
    try:
        from jose import jwt
        JWT_LIB = "python-jose"
    except ImportError:
        jwt = None
        JWT_LIB = None
        logging.warning("Neither PyJWT nor python-jose available. JWT signing will not work.")

logger = logging.getLogger(__name__)

class EpicFHIRService:
    """Service for storing processed documents in Epic FHIR system."""
    
    def __init__(self):
        """
        Initialize Epic FHIR service with configuration from environment variables.
        """
        # Default values
        default_fhir_server = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
        default_token_url = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
        default_scope = "openid profile fhirUser system/DocumentReference.Create Patient.Read Encounter.Read"  # Matches EPIC_SCOPES environment variable
        
        # Get environment variables with validation
        # Explicitly require backend Epic client values; avoid falling back to legacy VITE_* or built-in defaults
        legacy_client_id = os.getenv("VITE_EPIC_CLIENT_ID")
        env_client_id = os.getenv("EPIC_FHIR_CLIENT_ID") or os.getenv("EPIC_CLIENT_ID")
        if not env_client_id:
            if legacy_client_id:
                logger.warning("Ignoring VITE_EPIC_CLIENT_ID to prevent using legacy Epic app. Set EPIC_FHIR_CLIENT_ID or EPIC_CLIENT_ID.")
            self.client_id = None
        else:
            self.client_id = env_client_id
                         
        # Check both EPIC_FHIR_CLIENT_SECRET and EPIC_CLIENT_SECRET (do not fall back to VITE_* to avoid legacy app)
        self.client_secret = (os.getenv("EPIC_FHIR_CLIENT_SECRET") or 
                             os.getenv("EPIC_CLIENT_SECRET"))
        
        # Get JWKS URL dynamically from environment variables
        # Priority: 1. EPIC_FHIR_JWKS_URL (explicit), 2. Build from BASE_URL, 3. Build from APP_URL
        jwks_url_env = os.getenv("EPIC_FHIR_JWKS_URL")
        base_url = os.getenv("BASE_URL") or os.getenv("APP_URL") or os.getenv("PUBLIC_URL")
        
        if jwks_url_env and not jwks_url_env.startswith(("<", "YOUR_", "your_")) and jwks_url_env.startswith("http"):
            # Use explicitly provided JWKS URL
            self.jwks_url = jwks_url_env
        elif base_url and not base_url.startswith(("<", "YOUR_", "your_")):
            # Build JWKS URL from base URL
            base_url = base_url.rstrip('/')
            self.jwks_url = f"{base_url}/.well-known/jwks.json"
            logger.info(f"Built JWKS URL from BASE_URL: {self.jwks_url}")
        else:
            # Fallback: try to construct from server name or use a warning
            server_name = os.getenv("SERVER_NAME") or os.getenv("HOSTNAME")
            if server_name:
                protocol = "https" if os.getenv("USE_HTTPS", "true").lower() == "true" else "http"
                self.jwks_url = f"{protocol}://{server_name}/.well-known/jwks.json"
                logger.info(f"Built JWKS URL from SERVER_NAME: {self.jwks_url}")
            else:
                # Last resort: require explicit configuration
                self.jwks_url = None
                logger.warning("JWKS URL not configured. Set EPIC_FHIR_JWKS_URL, BASE_URL, or SERVER_NAME environment variable.")
        
        # Initialize key ID to None first (will be set if private key is loaded)
        self.jwks_key_id = None
        
        # For Backend Systems flow, we need private key for JWT signing
        # Private key path (PEM format)
        self.private_key_path = os.getenv("EPIC_FHIR_PRIVATE_KEY_PATH")
        self.private_key = None
        if self.private_key_path and os.path.exists(self.private_key_path):
            try:
                with open(self.private_key_path, 'rb') as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
                logger.info("Epic FHIR private key loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Epic FHIR private key: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
                self.private_key = None
        else:
            logger.warning("Epic FHIR private key path not provided or file not found")
            if self.private_key_path:
                logger.warning(f"  Attempted path: {self.private_key_path}")
    
        # Get FHIR server URL - check for placeholder values
        # Check EPIC_FHIR_SERVER_URL, then EPIC_AUDIENCE (often used as base URL), then default
        fhir_server_env = (os.getenv("EPIC_FHIR_SERVER_URL") or 
                          os.getenv("EPIC_AUDIENCE") or 
                          default_fhir_server)
                          
        if fhir_server_env and not fhir_server_env.startswith(("<", "YOUR_", "your_")):
            self.fhir_server_url = fhir_server_env
        else:
            self.fhir_server_url = default_fhir_server
            logger.warning(f"Epic FHIR Server URL was placeholder, using default: {self.fhir_server_url}")
        
        # Get token URL - check for placeholder values
        # Check EPIC_FHIR_TOKEN_URL, then EPIC_TOKEN_URL, then default
        token_url_env = (os.getenv("EPIC_FHIR_TOKEN_URL") or 
                        os.getenv("EPIC_TOKEN_URL") or 
                        default_token_url)
                        
        if token_url_env and not token_url_env.startswith(("<", "YOUR_", "your_")) and token_url_env.startswith("http"):
            self.token_url = token_url_env
        else:
            self.token_url = default_token_url
            logger.warning(f"Epic FHIR Token URL was placeholder or invalid, using default: {self.token_url}")
        
        self.scope = os.getenv("EPIC_FHIR_SCOPE") or os.getenv("EPIC_SCOPES") or default_scope
        
        self.access_token = None
        self.token_expires_at = None
        
        # Initialize key ID AFTER URLs are set (needed for JWT header)
        if self.private_key:
            self._initialize_key_id()
    
        # Validation and logging
        # For Backend Systems (JWT flow): Client Secret is NOT needed (Epic doesn't provide it)
        # For regular OAuth flow: Client Secret IS required
        if self.private_key:
            # Backend Systems flow - Client Secret is not used/needed
            if self.client_secret:
                logger.debug("Client Secret provided but not needed for Backend Systems (JWT) authentication")
        else:
            # Regular OAuth flow - Client Secret is required
            if not self.client_secret:
                logger.warning("Epic FHIR Client Secret not provided. Required for regular OAuth flow (not Backend Systems).")
            elif self.client_secret and self.client_secret.startswith(("<", "YOUR_", "your_")):
                logger.warning("Epic FHIR Client Secret appears to be a placeholder. Please set the actual secret.")
                self.client_secret = None
            else:
                # Client secret is provided and looks valid
                logger.debug("Epic FHIR Client Secret is configured")
        
        if not self.fhir_server_url or not self.fhir_server_url.startswith("http"):
            logger.warning("Epic FHIR Server URL not properly configured. FHIR integration will be disabled.")
        
        # Log configuration status with details
        logger.info("=" * 80)
        logger.info("EPIC FHIR SERVICE CONFIGURATION")
        logger.info("=" * 80)
        # SECURITY: Mask client_id in logs
        masked_client_id = f"{self.client_id[:4]}...{self.client_id[-4:]}" if self.client_id and len(self.client_id) > 8 else "***"
        logger.info(f"Client ID: {masked_client_id}")
        logger.info(f"Authentication Method: {'JWT (Backend Systems)' if self.private_key else 'Client Secret (Fallback)'}")
        logger.info(f"Private Key: {'LOADED' if self.private_key else 'NOT SET'}")
        logger.info(f"Client Secret: {'SET (' + str(len(self.client_secret)) + ' chars)' if self.client_secret else 'NOT SET'}")
        logger.info(f"FHIR Server URL: {self.fhir_server_url}")
        logger.info(f"Token URL: {self.token_url}")
        logger.info(f"Scope: {self.scope}")
        logger.info(f"Service Available: {self.is_available()}")
        logger.info("=" * 80)
        
        if self.is_available():
            if self.private_key:
                logger.info("✓ Epic FHIR service configured for Backend Systems (JWT) authentication")
            else:
                logger.warning("⚠ Epic FHIR service using Client Secret (not recommended for Backend Systems)")
                logger.warning("  For Backend Systems, configure EPIC_FHIR_PRIVATE_KEY_PATH for JWT authentication")
            logger.info("✓ Epic FHIR service is ready")
        else:
            logger.warning("✗ Epic FHIR service is NOT properly configured and will be disabled")
            if not self.client_id:
                logger.warning("  - Client ID is missing")
            if not self.private_key and not self.client_secret:
                logger.warning("  - Neither Private Key nor Client Secret is available")
            if not self.fhir_server_url:
                logger.warning("  - FHIR Server URL is missing")
    
    def _initialize_key_id(self):
        """Initialize the key ID (kid) from the private key's public key."""
        if not self.private_key:
            return
        
        try:
            public_key = self.private_key.public_key()
            import hashlib
            key_fingerprint = hashlib.sha256(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            ).hexdigest()[:16]
            self.jwks_key_id = key_fingerprint
            logger.info(f"Initialized key ID (kid): {key_fingerprint}")
        except Exception as e:
            logger.error(f"Failed to initialize key ID: {e}")
            self.jwks_key_id = None
    
    def get_jwks(self) -> Optional[Dict[str, Any]]:
        """
        Generate JWKS (JSON Web Key Set) from the public key.
        This is used to expose the public key for Epic to validate JWT signatures.
        
        Returns:
            Optional[Dict]: JWKS structure with public key, or None if private key not loaded
        """
        if not self.private_key:
            logger.error("Private key not loaded - cannot generate JWKS")
            return None
        
        try:
            # Get public key from private key
            public_key = self.private_key.public_key()
            public_numbers = public_key.public_numbers()
            
            # Convert to JWK format
            n_bytes = public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, 'big')
            e_bytes = public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, 'big')
            
            # Base64URL encode (RFC 7518)
            import base64
            def base64url_encode(data: bytes) -> str:
                return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')
            
            n_b64url = base64url_encode(n_bytes)
            e_b64url = base64url_encode(e_bytes)
            
            # Generate key ID from public key (first 8 chars of SHA256 hash)
            import hashlib
            key_fingerprint = hashlib.sha256(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            ).hexdigest()[:16]
            
            jwks = {
                "keys": [
                    {
                        "kty": "RSA",
                        "kid": key_fingerprint,
                        "n": n_b64url,
                        "e": e_b64url,
                        "alg": "RS256",
                        "use": "sig"
                    }
                ]
            }
            
            # Store key ID for use in JWT header
            self.jwks_key_id = key_fingerprint
            
            logger.debug(f"Generated JWKS with key ID: {key_fingerprint}")
            return jwks
            
        except Exception as e:
            logger.error(f"Failed to generate JWKS: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    def is_available(self) -> bool:
        """
        Check if Epic FHIR service is available and configured.
        
        For Backend Systems flow, we need client_id and private key (not client_secret).
        
        Returns:
            bool: True if service is configured and available, False otherwise
        """
        # For Backend Systems: need client_id and private key
        # For regular OAuth: need client_id and client_secret
        if self.private_key:
            return bool(self.client_id and self.private_key and self.fhir_server_url)
        else:
            # Fallback to client_secret if private key not available
            return bool(self.client_id and self.client_secret and self.fhir_server_url)
    
    def _create_signed_jwt(self) -> Optional[str]:
        """
        Create a signed JWT for Epic Backend Systems authentication.
        
        Epic requires:
        - Header with alg: RS256, typ: JWT, kid: matching JWKS key ID
        - Claims: iss, sub, aud (exact token URL), exp, iat, jti
        - Short expiry (60 seconds as recommended)
        
        Returns:
            Optional[str]: Signed JWT string if successful, None otherwise
        """
        if not jwt:
            logger.error("JWT library not available. Install PyJWT: pip install PyJWT cryptography")
            return None
        
        if not self.private_key:
            logger.error("Private key not available for JWT signing")
            return None
        
        try:
            # Get or generate key ID (kid) - must match JWKS
            if not self.jwks_key_id:
                # Generate key ID from public key
                public_key = self.private_key.public_key()
                import hashlib
                key_fingerprint = hashlib.sha256(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                ).hexdigest()[:16]
                self.jwks_key_id = key_fingerprint
            
            now = int(time.time())
            import uuid
            jti = str(uuid.uuid4())  # Unique token ID (UUID format)
            
            # JWT claims - Epic requires exact format per Backend Services specification
            # IMPORTANT: iss and sub must be the exact Client ID (no spaces, correct format)
            # aud must be the exact token URL for your Epic environment
            # nbf (not before) is REQUIRED by Epic - cannot be in future, exp-nbf <= 5 minutes
            claims = {
                "iss": self.client_id.strip(),  # Issuer = client ID (remove any whitespace)
                "sub": self.client_id.strip(),  # Subject = client ID (remove any whitespace)
                "aud": self.token_url.strip(),  # Audience = exact token URL (remove any whitespace)
                "jti": jti,  # JWT ID (unique per request - UUID format)
                "exp": now + 300,  # Expires in 300 seconds (5 minutes - Epic allows 60-300 seconds)
                "nbf": now - 60,  # Not before = 1 minute in past (Safeguard against clock skew)
                "iat": now  # Issued at
            }
            
            # JWT header with kid that matches JWKS
            # The kid MUST exactly match the kid in your JWKS endpoint
            headers = {
                "alg": "RS256",
                "typ": "JWT",
                "kid": self.jwks_key_id  # Must match the kid in JWKS exactly
            }
            
            # Log JWT details for debugging (without revealing the full signed JWT)
            logger.info(f"JWT Claims: iss={claims['iss']}, sub={claims['sub']}, aud={claims['aud']}, exp={claims['exp']}, nbf={claims['nbf']}, iat={claims['iat']}, jti={jti[:8]}...")
            logger.info(f"JWT Header: alg={headers['alg']}, typ={headers['typ']}, kid={headers['kid']}")
            
            # Sign JWT with private key and header
            if JWT_LIB == "PyJWT":
                signed_jwt = jwt.encode(
                    claims,
                    self.private_key,
                    algorithm="RS256",
                    headers=headers
                )
                # PyJWT returns string in newer versions, but ensure it's always a string
                if isinstance(signed_jwt, bytes):
                    signed_jwt = signed_jwt.decode('utf-8')
            else:  # python-jose
                # python-jose doesn't support headers parameter the same way
                signed_jwt = jwt.encode(
                    claims,
                    self.private_key,
                    algorithm="RS256"
                )
                # Note: python-jose may need different approach for kid in header
                if isinstance(signed_jwt, bytes):
                    signed_jwt = signed_jwt.decode('utf-8')
            
            # Ensure signed_jwt is a string (not bytes)
            if not isinstance(signed_jwt, str):
                signed_jwt = str(signed_jwt)
            
            logger.info(f"✓ Created signed JWT with jti: {jti}, kid: {self.jwks_key_id}, expires in 300s using {JWT_LIB}")
            
            # For debugging: decode and log JWT structure (verify it's correct)
            try:
                # Decode without verification to show structure
                decoded = jwt.decode(signed_jwt, options={"verify_signature": False})
                logger.debug(f"JWT Structure verified: {len(decoded)} claims, exp in {decoded.get('exp', 0) - now} seconds")
                
                # Verify all required claims are present (per Epic Backend Services spec)
                required_claims = ['iss', 'sub', 'aud', 'exp', 'nbf', 'iat', 'jti']
                missing_claims = [claim for claim in required_claims if claim not in decoded]
                if missing_claims:
                    logger.warning(f"Missing JWT claims: {missing_claims}")
                else:
                    logger.debug("✓ All required JWT claims present (iss, sub, aud, exp, nbf, iat, jti)")
            except Exception as e:
                logger.warning(f"Could not decode JWT for verification: {e}")
            
            return signed_jwt
            
        except Exception as e:
            logger.error(f"Failed to create signed JWT: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _get_access_token(self) -> Optional[str]:
        """
        Get OAuth2 access token from Epic FHIR authorization server.
        
        Returns:
            Optional[str]: Access token if successful, None otherwise
        """
        if not self.is_available():
            logger.error("Epic FHIR service is not properly configured")
            return None
        
        # Check if we have a valid cached token
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token
        
        try:
            # Validate token URL before making request
            if not self.token_url or not self.token_url.startswith("http"):
                logger.error(f"Invalid Epic FHIR Token URL: {self.token_url}")
                return None
            
            # OAuth2 token request - Epic Backend Systems uses JWT assertion
            # Check if we have private key for Backend Systems flow
                # Prepare credentials - defensive stripping of whitespace and quotes
                clean_client_id = self.client_id.strip().strip('"').strip("'")
                
                # Verify we have the private key for signing
                if not self.private_key:
                    logger.error("Private key missing for JWT flow during execution")
                    return None

                # Backend Systems flow: Use signed JWT (REQUIRED for Backend Systems)
                logger.info(f"Using JWT Backend Systems authentication (private_key_jwt)")
                logger.info(f"Requesting access token from Epic FHIR at: {self.token_url}")
                # SECURITY: Mask client_id in logs
                masked_client_id = f"{clean_client_id[:4]}...{clean_client_id[-4:]}" if clean_client_id and len(clean_client_id) > 8 else "***"
                logger.info(f"Client ID: {masked_client_id}")
                logger.info(f"Scope: {self.scope}")
                logger.info(f"Key ID (kid): {self.jwks_key_id}")
                
                # Create signed JWT with CLEAN client ID
                # We need to temporarily patch self.client_id or pass it (but method uses self.client_id)
                original_client_id = self.client_id
                self.client_id = clean_client_id
                try:
                    signed_jwt = self._create_signed_jwt()
                finally:
                    self.client_id = original_client_id
                
                if not signed_jwt:
                    logger.error("Failed to create signed JWT for Backend Systems authentication")
                    return None
                
                # Decode JWT for debugging (to verify what we're sending to Epic)
                try:
                    decoded = jwt.decode(signed_jwt, options={"verify_signature": False})
                    logger.info("=" * 80)
                    logger.info("JWT DEBUG INFO (For Epic Support Ticket)")
                    logger.info("=" * 80)
                    logger.info(f"JWT Header (decoded): {json.dumps({'alg': 'RS256', 'typ': 'JWT', 'kid': self.jwks_key_id}, indent=2)}")
                    logger.info(f"JWT Payload (decoded): {json.dumps(decoded, indent=2)}")
                    logger.info(f"JWT iss (Client ID): {decoded.get('iss')}")
                    logger.info(f"JWT sub (Client ID): {decoded.get('sub')}")
                    logger.info(f"JWT aud (Token URL): {decoded.get('aud')}")
                    logger.info(f"JWT kid (Key ID): {self.jwks_key_id}")
                    logger.info(f"JWKS URL: {self.jwks_url or 'NOT CONFIGURED'}")
                    logger.info("=" * 80)
                except Exception as e:
                    logger.warning(f"Could not decode JWT for debugging: {e}")
                
                # Epic Backend Systems: Use JWT assertion
                # Per Epic documentation: DO NOT include client_id in request body
                # Epic derives the client ID from the JWT's iss/sub claims
                # Required parameters: grant_type, client_assertion_type, client_assertion, scope
                
                # CRITICAL: For Backend Systems, remove user-specific scopes (openid, profile, fhirUser)
                # These are only valid for user-context flows (SMART on FHIR)
                # Backend Systems flow uses system/*.Create, Patient.Read, Encounter.Read scopes
                backend_scope = self.scope
                if "openid" in backend_scope or "fhirUser" in backend_scope:
                    logger.info(f"Filtering user scopes from '{backend_scope}' for Backend Systems flow")
                    scopes_list = backend_scope.split()
                    # Keep system/* scopes, Patient.Read, Encounter.Read, and DocumentReference.Create
                    # Remove only user-specific scopes: openid, profile, email, fhirUser
                    filtered_scopes = [s for s in scopes_list if s not in ['openid', 'profile', 'email', 'fhirUser'] and not s.startswith('launch')]
                    backend_scope = " ".join(filtered_scopes)
                    
                    # Ensure we have the required scopes
                    required_scopes = []
                    if 'system/DocumentReference.Create' not in backend_scope and 'DocumentReference.Create' not in backend_scope:
                        required_scopes.append('system/DocumentReference.Create')
                    if 'Patient.Read' not in backend_scope:
                        required_scopes.append('Patient.Read')
                    if 'Encounter.Read' not in backend_scope:
                        required_scopes.append('Encounter.Read')
                    
                    if required_scopes:
                        backend_scope = f"{backend_scope} {' '.join(required_scopes)}".strip()
                        logger.info(f"Added required scopes: {required_scopes}")
                    
                    logger.info(f"Using sanitized Backend Systems scope: {backend_scope}")

                token_data = {
                    "grant_type": "client_credentials",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": signed_jwt,
                    "scope": backend_scope
                }
                
                logger.info(f"Token request (Backend Systems JWT flow - per Epic spec):")
                logger.info(f"  URL: {self.token_url}")
                logger.info(f"  Grant Type: client_credentials")
                logger.info(f"  Client Assertion Type: urn:ietf:params:oauth:client-assertion-type:jwt-bearer")
                logger.info(f"  Scope: {backend_scope}")
                logger.info(f"  JWT length: {len(signed_jwt)} characters")
                logger.info(f"  ✓ NOT including client_id (Epic derives from JWT iss/sub claims)")
                
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                }
                
                # Attempt JWT Authentication
                response = requests.post(
                    self.token_url,
                    data=token_data,
                    headers=headers,
                    timeout=30
                )
                
                # Check if JWT auth succeeded
                if response.status_code == 200:
                    logger.info("✓ JWT Authentication successful")
                elif response.status_code in [400, 401] and self.client_secret:
                    # If JWT auth failed and we have a secret, try Client Credentials Fallback
                    logger.warning(f"JWT Authentication failed ({response.status_code}). Attempting Client Secret fallback...")
                    logger.warning(f"JWT Error: {response.text[:200]}")
                    
                    # Prepare Client Credentials Request with CLEANED credentials
                    clean_secret = self.client_secret.strip().strip('"').strip("'")
                    
                    fallback_data = {
                        "grant_type": "client_credentials",
                        "client_id": clean_client_id, # Use the cleaned ID from above
                        "client_secret": clean_secret,
                        "scope": backend_scope  # Use the same sanitized scope
                    }
                    
                    logger.info("Functioning Fallback: Requesting token with Client Secret")
                    response = requests.post(
                        self.token_url,
                        data=fallback_data,
                        headers=headers,
                        timeout=30
                    )
                else:
                    # JWT failed and no secret to fall back to (or other error)
                    pass # logic continues to handle response based on whatever 'response' holds now

                # Log response details
                logger.debug(f"Token response status: {response.status_code}")
                logger.debug(f"Token response headers: {dict(response.headers)}")
            else:
                # Fallback: Regular OAuth flow with client_secret (No private key flow)
                if not self.client_secret:
                    logger.error("Neither private key nor client_secret available")
                    return None
                
                token_data = {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.scope
                }
                
                logger.debug(f"Token request details (Regular OAuth flow):")
                logger.debug(f"  URL: {self.token_url}")
                logger.debug(f"  Grant Type: client_credentials")
                # SECURITY: Mask client_id in logs
                masked_client_id = f"{self.client_id[:4]}...{self.client_id[-4:]}" if self.client_id and len(self.client_id) > 8 else "***"
                logger.debug(f"  Client ID: {masked_client_id}")
                logger.debug(f"  Scope: {self.scope}")
                logger.debug(f"  Client Secret Length: {len(self.client_secret)}")
                
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                }
                
                response = requests.post(
                    self.token_url,
                    data=token_data,
                    headers=headers,
                    timeout=30
                )
                
                # Log response details
                logger.debug(f"Token response status: {response.status_code}")
                logger.debug(f"Token response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    token_response = response.json()
                    self.access_token = token_response.get("access_token")
                    expires_in = token_response.get("expires_in", 3600)  # Default to 1 hour
                    
                    if not self.access_token:
                        logger.error("Access token not found in response")
                        logger.error(f"Response content: {token_response}")
                        return None
                    
                    # Set expiration time (subtract 60 seconds for safety margin)
                    from datetime import timedelta
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                    
                    logger.info(f"✓ Successfully obtained Epic FHIR access token (expires in {expires_in}s)")
                    # SECURITY: Never log access tokens, even partially
                    # Removed token preview to prevent credential leakage
                    return self.access_token
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse token response as JSON: {e}")
                    logger.error(f"Response text: {response.text[:500]}")
                    return None
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = json.dumps(error_json, indent=2)
                    
                    # Provide specific guidance based on error
                    error_type = error_json.get("error", "")
                    error_desc = error_json.get("error_description", "")
                    
                    # Log full error response for debugging
                    logger.error("=" * 80)
                    logger.error("EPIC FHIR TOKEN REQUEST FAILED")
                    logger.error("=" * 80)
                    logger.error(f"HTTP Status: {response.status_code}")
                    logger.error(f"Error Type: {error_type}")
                    logger.error(f"Error Description: {error_desc if error_desc else 'None provided'}")
                    logger.error(f"Full Error Response: {error_detail}")
                    logger.error("=" * 80)
                    logger.error("CRITICAL CHECKLIST - Verify ALL of these in Epic App Orchard:")
                    logger.error("  1. Application Audience = 'Backend Systems' (NOT 'Patients')")
                    logger.error("  2. Status = 'Ready' or 'Active' (save after changing)")
                    logger.error("  3. Incoming APIs: Ensure all required APIs are SELECTED:")
                    logger.error("     - 'DocumentReference' API (enables POST/create operations)")
                    logger.error("     - 'Patient' API (enables GET/read operations)")
                    logger.error("     - 'Encounter' API (enables GET/read operations)")
                    logger.error(f"  4. Non-Production Client ID = '{self.client_id}' (must match exactly)")
                    logger.error(f"  5. JWK Set URL = '{self.jwks_url or 'NOT CONFIGURED'}'")
                    logger.error("  6. JWKS URL must show 'Valid' when you click Validate button")
                    logger.error(f"  7. JWKS kid '{self.jwks_key_id}' must match the kid in your JWKS endpoint")
                    logger.error(f"  8. Token URL '{self.token_url}' must be correct for your Epic environment")
                    logger.error("=" * 80)
                    
                    if error_type == "invalid_client":
                        logger.error("=" * 80)
                        logger.error("EPIC FHIR AUTHENTICATION FAILED: invalid_client")
                        logger.error("=" * 80)
                        logger.error("Possible causes:")
                        logger.error("  1. Client ID is incorrect or doesn't exist")
                        logger.error("  2. Client Secret is incorrect or doesn't match Client ID")
                        logger.error("  3. Client ID and Client Secret are from different apps")
                        logger.error("  4. App is not activated/approved in Epic App Orchard")
                        logger.error("  5. Backend server wasn't restarted after updating .env file")
                        logger.error("")
                        logger.error(f"Current Client ID: {self.client_id}")
                        logger.error(f"Current Token URL: {self.token_url}")
                        logger.error(f"Current Scope: {self.scope}")
                        logger.error("")
                        logger.error("What to check:")
                        logger.error("  1. Verify Client ID in Epic App Orchard matches exactly")
                        logger.error("")
                        logger.error("SPECIFIC STEPS TO FIX invalid_client:")
                        logger.error("  1. Open Epic App Orchard: https://apporchard.epic.com/")
                        logger.error("  2. Find your app with Client ID: " + self.client_id)
                        logger.error("  3. Go to Configuration/Settings")
                        logger.error("  4. Verify Application Audience = 'Backend Systems'")
                        logger.error("  5. Set Status = 'Ready' (then click Save)")
                        logger.error("  6. Under Incoming APIs: Ensure all required APIs are SELECTED:")
                        logger.error("     - 'DocumentReference' API (enables POST/create operations)")
                        logger.error("     - 'Patient' API (enables GET/read operations)")
                        logger.error("     - 'Encounter' API (enables GET/read operations)")
                        logger.error("  7. Under Non-Production section:")
                        logger.error(f"     - Verify Client ID matches: {self.client_id}")
                        logger.error(f"     - Set JWK Set URL: {self.jwks_url or 'NOT CONFIGURED'}")
                        logger.error("     - Click 'Validate' button - MUST show green/success")
                        logger.error("  8. Save all changes")
                        logger.error("  9. Wait 5-10 minutes for Epic to sync")
                        logger.error("  10. Test again")
                        logger.error("")
                        logger.error("If still failing after all above steps, contact Epic support with:")
                        logger.error(f"  - App/Client ID: {self.client_id}")
                        logger.error(f"  - JWKS URL: {self.jwks_url or 'NOT CONFIGURED'}")
                        logger.error(f"  - JWKS kid: {self.jwks_key_id}")
                        logger.error("  - Screenshot of JWKS validation success")
                        logger.error("  - JWT header and payload (see logs above)")
                        logger.error("=" * 80)
                    elif error_type == "invalid_scope":
                        logger.error(f"Invalid scope error: {error_desc}")
                        logger.error(f"Current scope: {self.scope}")
                        logger.error("Check if your Epic app has the required scopes/permissions")
                    elif error_type == "invalid_grant":
                        logger.error(f"Invalid grant error: {error_desc}")
                        logger.error("Check if client_credentials grant type is enabled for your app")
                    
                except:
                    pass
                
                logger.error(f"Failed to get access token: {response.status_code}")
                logger.error(f"Response: {error_detail[:1000]}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting Epic FHIR access token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting Epic FHIR access token: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    def search_patient_by_identifier(self, member_id: str) -> Optional[str]:
        """
        Search for Epic Patient ID using member ID or other identifier.
        
        This method searches Epic FHIR API for a patient using various identifier systems.
        Requires Patient.Read permission in Epic app scopes.
        
        Args:
            member_id: Member ID or other identifier to search for
            
        Returns:
            Optional[str]: Epic Patient ID if found, None otherwise
        """
        if not self.is_available():
            logger.error("Epic FHIR service is not properly configured")
            return None
        
        # Get access token
        access_token = self._get_access_token()
        if not access_token:
            logger.error("Failed to obtain access token for patient search")
            return None
        
        try:
            # Try multiple identifier systems to find the patient
            identifier_systems = [
                f"MB|{member_id}",  # Member ID system
                f"http://hl7.org/fhir/sid/us-medicare|{member_id}",  # Medicare ID
                f"http://hl7.org/fhir/sid/us-ssn|{member_id}",  # SSN
                member_id  # Plain identifier (Epic may auto-detect)
            ]
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/fhir+json"
            }
            
            for identifier in identifier_systems:
                try:
                    # Search for patient by identifier
                    search_url = f"{self.fhir_server_url}/Patient"
                    params = {"identifier": identifier}
                    
                    logger.info(f"Searching for patient with identifier: {identifier}")
                    
                    response = requests.get(
                        search_url,
                        params=params,
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        try:
                            bundle = response.json()
                            
                            # Check if we found any patients
                            if bundle.get("resourceType") == "Bundle":
                                entries = bundle.get("entry", [])
                                
                                if entries:
                                    # Get the first patient's ID
                                    patient_resource = entries[0].get("resource", {})
                                    epic_patient_id = patient_resource.get("id")
                                    
                                    if epic_patient_id:
                                        # SECURITY/HIPAA: Avoid logging any patient or member identifiers
                                        logger.info("✓ Found Epic Patient in FHIR server for provided identifiers.")
                                        return epic_patient_id
                                else:
                                    logger.debug(f"No patient found with identifier: {identifier}")
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse patient search response: {e}")
                            continue
                    elif response.status_code == 403:
                        logger.warning("Patient.Read permission not available. Add Patient.Read to Epic app scopes.")
                        return None
                    else:
                        logger.debug(f"Patient search failed with status {response.status_code} for identifier: {identifier}")
                        
                except requests.exceptions.RequestException as e:
                    logger.debug(f"Network error searching for patient with identifier {identifier}: {e}")
                    continue
            
            # If we get here, no patient was found with any identifier system
            # SECURITY/HIPAA: Mask PHI in logs
            masked_member_id = f"{member_id[:3]}...{member_id[-3:]}" if member_id and len(member_id) > 6 else "***"
            logger.warning(f"✗ No Epic Patient ID found for member ID: {masked_member_id}")
            logger.warning("  Possible causes:")
            logger.warning("  1. Patient doesn't exist in Epic system")
            logger.warning("  2. Member ID is incorrect")
            logger.warning("  3. Identifier system doesn't match Epic's configuration")
            logger.warning("  4. Patient.Read permission not granted")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for patient: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _create_observation(self, processed_data: Dict[str, Any], filename: str, 
                           tenant_id: str, processing_id: str) -> Dict[str, Any]:
        """
        Create a FHIR Observation resource from processed document data.
        
        Stores only the key-value pairs as JSON in the Observation value.
        Uses DocumentReference API (POST/create operation) which is available in the current Epic app configuration.
        
        Args:
            processed_data: The processed document data with key-value pairs
            filename: Original filename
            tenant_id: Tenant identifier
            processing_id: Processing identifier
            
        Returns:
            Dict containing the FHIR Observation resource
        """
        current_time = datetime.now().isoformat()
        
        # Extract only key-value pairs
        key_value_pairs = processed_data.get("key_value_pairs", {})
        
        # Convert key-value pairs to JSON string
        key_value_pairs_json = json.dumps(key_value_pairs, indent=2, ensure_ascii=False)
        
        # Create FHIR Observation resource with key-value pairs as value
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "document",
                            "display": "Document"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11503-0",
                        "display": "Progress note"
                    }
                ],
                "text": f"Processed Document: {filename}"
            },
            "subject": {
                "reference": f"Patient/{tenant_id}"  # You may need to map tenant_id to actual patient ID
            },
            "effectiveDateTime": current_time,
            "issued": current_time,
            "valueString": key_value_pairs_json,
            "note": [
                {
                    "text": f"Extracted key-value pairs from document: {filename}"
                }
            ],
            "extension": [
                {
                    "url": "http://hl7.org/fhir/StructureDefinition/observation-processing-metadata",
                    "extension": [
                        {
                            "url": "processingId",
                            "valueString": processing_id
                        },
                        {
                            "url": "filename",
                            "valueString": filename
                        }
                    ]
                }
            ]
        }
        
        return observation
    
    def store_document(self, processed_data: Dict[str, Any], filename: str, 
                      tenant_id: str, processing_id: str) -> Dict[str, Any]:
        """
        Store processed document data in Epic FHIR system.
        
        Args:
            processed_data: The processed document data with key-value pairs and metadata
            filename: Original filename
            tenant_id: Tenant identifier
            processing_id: Processing identifier
            
        Returns:
            Dict with success status and response details
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "Epic FHIR service is not properly configured",
                "skipped": True
            }
        
        try:
            # Get access token
            access_token = self._get_access_token()
            if not access_token:
                return {
                    "success": False,
                    "error": "Failed to obtain access token",
                    "skipped": False
                }
            
            # Try to find Epic Patient ID from extracted data
            # Look for Member ID, Patient ID, or similar fields in key-value pairs
            key_value_pairs = processed_data.get('key_value_pairs', {})
            epic_patient_id = None
            member_id = None
            
            # Check for explicit Epic Patient ID first
            for key in ['Epic Patient ID', 'epic_patient_id', 'patient_id', 'Patient ID']:
                if key in key_value_pairs:
                    potential_id = str(key_value_pairs[key]).strip()
                    # Epic Patient IDs are alphanumeric (not purely numeric)
                    if potential_id and not potential_id.isdigit():
                        epic_patient_id = potential_id
                        # SECURITY/HIPAA: Avoid logging patient identifiers, even in masked form
                        logger.info("Using Epic Patient ID from extracted data.")
                        break
            
            # If no Epic Patient ID found, try to search by Member ID
            if not epic_patient_id:
                for key in ['Member ID', 'member_id', 'MemberID', 'Medicare ID', 'medicare_id']:
                    if key in key_value_pairs:
                        member_id = str(key_value_pairs[key]).strip()
                        if member_id and member_id.isdigit():
                            # SECURITY/HIPAA: Mask PHI in logs
                            masked_member_id = f"{member_id[:3]}...{member_id[-3:]}" if member_id and len(member_id) > 6 else "***"
                            logger.info(f"Found Member ID in extracted data: {masked_member_id}")
                            logger.info(f"Searching for Epic Patient ID using Member ID: {masked_member_id}")
                            
                            # Search for Epic Patient ID using member ID
                            epic_patient_id = self.search_patient_by_identifier(member_id)
                            
                            if epic_patient_id:
                                # SECURITY/HIPAA: Mask PHI in logs (do not log raw identifiers)
                                masked_member_id = f"{member_id[:3]}...{member_id[-3:]}" if member_id and len(member_id) > 6 else "***"
                                masked_patient_id = f"{epic_patient_id[:3]}...{epic_patient_id[-3:]}" if epic_patient_id and len(epic_patient_id) > 6 else "***"
                                logger.info("✓ Successfully mapped extracted Member ID to an Epic Patient ID.")
                                # Add Epic Patient ID to the key-value pairs for storage
                                key_value_pairs['Epic Patient ID'] = epic_patient_id
                                processed_data['key_value_pairs'] = key_value_pairs
                            else:
                                # SECURITY/HIPAA: Mask PHI in logs
                                masked_member_id = f"{member_id[:3]}...{member_id[-3:]}" if member_id and len(member_id) > 6 else "***"
                                logger.warning(f"✗ Could not find Epic Patient ID for Member ID: {masked_member_id}")
                                logger.warning("  Will use tenant_id as fallback (may fail if not a valid Epic Patient ID)")
                            break
            
            # If still no Epic Patient ID, use tenant_id as fallback (original behavior)
            if not epic_patient_id:
                epic_patient_id = tenant_id
                # SECURITY: Do not log tenant_id or any portion of it
                logger.warning("No Epic Patient ID found. Using tenant_id as fallback (value redacted).")
                logger.warning("  This may fail if tenant_id is not a valid Epic Patient ID")
            
            # Create FHIR Observation with key-value pairs as JSON content
            # Using DocumentReference API (POST/create operation) which matches the Epic app configuration
            observation = self._create_observation(
                processed_data=processed_data,
                filename=filename,
                tenant_id=epic_patient_id,  # Use the Epic Patient ID we found
                processing_id=processing_id
            )
            
            # Store in Epic FHIR
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json"
            }
            
            # Validate FHIR server URL
            if not self.fhir_server_url or not self.fhir_server_url.startswith("http"):
                error_msg = f"Invalid Epic FHIR Server URL: {self.fhir_server_url}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "skipped": False
                }
            
            fhir_endpoint = f"{self.fhir_server_url}/Observation"
            logger.info(f"Storing key-value pairs in Epic FHIR as Observation: {filename}")
            logger.info(f"FHIR Endpoint: {fhir_endpoint}")
            
            key_value_pairs = processed_data.get('key_value_pairs', {})
            logger.debug(f"Key-value pairs count: {len(key_value_pairs)}")
            if key_value_pairs:
                logger.debug(f"Sample keys: {list(key_value_pairs.keys())[:5]}")
            
            try:
                response = requests.post(
                    fhir_endpoint,
                    json=observation,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    try:
                        response_data = response.json()
                        fhir_id = response_data.get("id", "unknown")
                        logger.info(f"✓ Successfully stored key-value pairs in Epic FHIR as Observation - ID: {fhir_id}")
                        
                        return {
                            "success": True,
                            "fhir_id": fhir_id,
                            "fhir_version_id": response_data.get("meta", {}).get("versionId"),
                            "message": "Key-value pairs successfully stored in Epic FHIR as Observation",
                            "observation": response_data
                        }
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse Epic FHIR response as JSON: {response.text[:200]}")
                        return {
                            "success": False,
                            "error": "Invalid JSON response from Epic FHIR",
                            "status_code": response.status_code,
                            "response": response.text[:500]
                        }
                else:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = json.dumps(error_json, indent=2)
                    except:
                        pass
                    
                    error_msg = f"Failed to store key-value pairs in Epic FHIR as Observation: {response.status_code}"
                    logger.error(error_msg)
                    logger.error(f"Response: {error_detail[:500]}")
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "error_detail": error_detail[:500],
                        "status_code": response.status_code,
                        "response": error_detail
                    }
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error storing in Epic FHIR: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "skipped": False
                }
                
        except Exception as e:
            error_msg = f"Error storing key-value pairs in Epic FHIR as Observation: {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "skipped": False
            }
    
    def store_document_binary(self, processed_data: Dict[str, Any], filename: str,
                             tenant_id: str, processing_id: str) -> Dict[str, Any]:
        """
        Store processed document as binary data in Epic FHIR (alternative approach).
        
        This method stores the entire processed JSON as binary data in FHIR.
        
        Args:
            processed_data: The processed document data
            filename: Original filename
            tenant_id: Tenant identifier
            processing_id: Processing identifier
            
        Returns:
            Dict with success status and response details
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "Epic FHIR service is not properly configured",
                "skipped": True
            }
        
        try:
            # Get access token
            access_token = self._get_access_token()
            if not access_token:
                return {
                    "success": False,
                    "error": "Failed to obtain access token",
                    "skipped": False
                }
            
            # Create Binary resource with only key-value pairs
            import base64
            key_value_pairs = processed_data.get("key_value_pairs", {})
            json_data = json.dumps(key_value_pairs, indent=2, ensure_ascii=False)
            base64_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
            
            binary_resource = {
                "resourceType": "Binary",
                "contentType": "application/json",
                "content": base64_data
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json"
            }
            
            logger.info(f"Storing key-value pairs binary in Epic FHIR: {filename}")
            logger.debug(f"Key-value pairs being stored: {key_value_pairs}")
            
            response = requests.post(
                f"{self.fhir_server_url}/Binary",
                json=binary_resource,
                headers=headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                response_data = response.json()
                binary_id = response_data.get("id")
                
                # Now create DocumentReference pointing to the Binary
                document_reference = self._create_document_reference(
                    processed_data=processed_data,
                    filename=filename,
                    tenant_id=tenant_id,
                    processing_id=processing_id,
                    binary_id=binary_id
                )
                
                # Store DocumentReference
                doc_response = requests.post(
                    f"{self.fhir_server_url}/DocumentReference",
                    json=document_reference,
                    headers=headers,
                    timeout=30
                )
                
                if doc_response.status_code in [200, 201]:
                    doc_data = doc_response.json()
                    logger.info(f"Successfully stored key-value pairs in Epic FHIR: {doc_data.get('id', 'unknown')}")
                    
                    return {
                        "success": True,
                        "fhir_id": doc_data.get("id"),
                        "binary_id": binary_id,
                        "fhir_version_id": doc_data.get("meta", {}).get("versionId"),
                        "message": "Key-value pairs successfully stored in Epic FHIR",
                        "document_reference": doc_data
                    }
                else:
                    error_msg = f"Failed to store DocumentReference: {doc_response.status_code} - {doc_response.text}"
                    logger.error(error_msg)
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "binary_id": binary_id,
                        "status_code": doc_response.status_code
                    }
            else:
                error_msg = f"Failed to store binary in Epic FHIR: {response.status_code} - {response.text}"
                logger.error(error_msg)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code,
                    "response": response.text
                }
                
        except Exception as e:
            error_msg = f"Error storing key-value pairs binary in Epic FHIR: {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "skipped": False
            }

