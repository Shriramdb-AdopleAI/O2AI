from sqlalchemy.orm import Session
from models.database import User, get_db, engine
from auth.auth_utils import get_password_hash
import logging

logger = logging.getLogger(__name__)

def create_default_admin():
    """Create default admin account if it doesn't exist, or update existing admin@o2.ai user."""
    db = Session(engine)
    try:
        # Check if admin user exists by username
        admin_user = db.query(User).filter(User.username == "admin").first()
        
        # Also check if admin@o2.ai exists (might have different username)
        admin_email_user = db.query(User).filter(User.email == "admin@o2.ai").first()
        
        if admin_user:
            # Update existing admin user to ensure is_admin is True
            if not admin_user.is_admin:
                admin_user.is_admin = True
                db.commit()
                logger.info("Updated existing admin user to have admin privileges")
            else:
                logger.info("Admin account already exists with admin privileges")
            return True
        elif admin_email_user:
            # Update existing admin@o2.ai user to have admin privileges
            if not admin_email_user.is_admin:
                admin_email_user.is_admin = True
                db.commit()
                logger.info(f"Updated user {admin_email_user.email} to have admin privileges")
            # Also ensure username is "admin" if it's not
            if admin_email_user.username != "admin":
                admin_email_user.username = "admin"
                db.commit()
                logger.info(f"Updated username to 'admin' for {admin_email_user.email}")
            return True
        else:
            # Create new default admin
            admin_user = User(
                username="admin",
                email="admin@o2.ai",
                hashed_password=get_password_hash("admin123"),  # Default password
                is_active=True,
                is_admin=True
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            logger.info("Default admin account created")
            # logger.info("Username: admin")
            # logger.info("Password: admin123")
            # logger.info("Email: admin@o2.ai")
            # logger.info("WARNING: Please change the default password after first login!")
            
            return True
            
    except Exception as e:
        logger.error(f"Error creating admin account: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def create_test_user():
    """Create a test user account."""
    db = Session(engine)
    try:
        # Check if test user already exists
        test_user = db.query(User).filter(User.username == "testuser").first()
        
        if not test_user:
            # Create test user
            test_user = User(
                username="testuser",
                email="test@o2.ai",
                hashed_password=get_password_hash("test123"),
                is_active=True,
                is_admin=False
            )
            
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            
            logger.info("Test user account created")
            # logger.info("Username: testuser")
            # logger.info("Password: test123")
            # logger.info("Email: test@o2.ai")
            
            return True
        else:
            logger.info("Test user account already exists")
            return False
            
    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def create_or_update_admin_email():
    """Create or update user with admin email to have admin access."""
    db = Session(engine)
    try:
        admin_email = "krish@elevancesystems.com"
        
        # Check if user with this email already exists
        admin_user = db.query(User).filter(User.email == admin_email.lower()).first()
        
        if admin_user:
            # Ensure user is active (same access as testuser through get_testuser_or_admin_user)
            if not admin_user.is_active:
                admin_user.is_active = True
                db.commit()
                logger.info(f"Updated user {admin_email} to be active (testuser-level access)")
            else:
                logger.info(f"User {admin_email} already exists and is active (testuser-level access)")
            return True
        else:
            # Create new admin user
            # Generate username from email
            username_base = admin_email.split('@')[0]
            username = username_base
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{username_base}{counter}"
                counter += 1
            
            admin_user = User(
                username=username,
                email=admin_email.lower(),
                hashed_password=get_password_hash("admin123"),  # Default password
                is_active=True,
                is_admin=False  # Same as testuser - access through get_testuser_or_admin_user
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            logger.info(f"Created admin user account for {admin_email}")
            return True
            
    except Exception as e:
        logger.error(f"Error creating/updating admin email user: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    create_default_admin()
    create_test_user()
    create_or_update_admin_email()
