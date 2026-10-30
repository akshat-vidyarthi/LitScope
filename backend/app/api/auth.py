from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """
    Registers a new user account.
    The first registered user is automatically designated as 'owner'.
    Subsequent users default to 'viewer'.
    """
    email_clean = payload.email.strip().lower()

    # 1. Check if email already registered
    existing = db.execute(
        text("SELECT id FROM users WHERE email = :email;"),
        {"email": email_clean}
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{email_clean}' already exists."
        )

    # 2. Check total users count: first user becomes owner
    user_count = db.execute(text("SELECT COUNT(*) FROM users;")).scalar() or 0
    assigned_role = "owner" if user_count == 0 else "viewer"

    # 3. Hash password
    hashed_pwd = hash_password(payload.password)

    # 4. Insert into database
    sql = text("""
        INSERT INTO users (email, full_name, hashed_password, role, is_active)
        VALUES (:email, :full_name, :hashed_password, :role, TRUE)
        RETURNING id, email, full_name, role, is_active, created_at;
    """)

    result = db.execute(
        sql,
        {
            "email": email_clean,
            "full_name": payload.full_name.strip() if payload.full_name else None,
            "hashed_password": hashed_pwd,
            "role": assigned_role
        }
    )
    user_row = result.mappings().fetchone()

    # 5. Log audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, action, details)
            VALUES (:user_id, 'user_registered', :details);
        """),
        {
            "user_id": user_row["id"],
            "details": f'{{"email": "{email_clean}", "role": "{assigned_role}"}}'
        }
    )
    db.commit()
    return user_row


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user with email and password.
    Returns a signed JWT access token.
    """
    email_clean = payload.email.strip().lower()

    # 1. Fetch user by email
    sql = text("""
        SELECT id, email, full_name, hashed_password, role, is_active, created_at
        FROM users
        WHERE email = :email;
    """)
    user = db.execute(sql, {"email": email_clean}).mappings().fetchone()

    # 2. Verify existence and password hash
    if not user or not user["hashed_password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )

    # 3. Generate JWT access token
    access_token = create_access_token(
        data={
            "sub": str(user["id"]),
            "email": user["email"],
            "role": user["role"]
        }
    )

    # 4. Log audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, action, details)
            VALUES (:user_id, 'user_login', '{"method": "password"}');
        """),
        {"user_id": user["id"]}
    )
    db.commit()

    user_info = {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
    }

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_info
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user."""
    return current_user
