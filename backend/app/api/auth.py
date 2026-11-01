from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse, UserSearchResult

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """
    Registers a new user account with a unique username and password.
    The first registered user is automatically designated as 'owner'.
    Subsequent users default to 'viewer'.
    """
    username_clean = payload.username.strip().lower()

    # 1. Check if username already registered
    existing_username = db.execute(
        text("SELECT id FROM users WHERE LOWER(username) = :username;"),
        {"username": username_clean}
    ).fetchone()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The username '{payload.username.strip()}' is already taken."
        )

    # 2. Check email if provided
    email_clean = payload.email.strip().lower() if payload.email and payload.email.strip() else None
    if email_clean:
        existing_email = db.execute(
            text("SELECT id FROM users WHERE LOWER(email) = :email;"),
            {"email": email_clean}
        ).fetchone()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with email '{email_clean}' already exists."
            )

    # 3. Check non-test users count: first real user becomes owner
    user_count = db.execute(
        text("SELECT COUNT(*) FROM users WHERE username NOT LIKE 'test_%' AND (email IS NULL OR email NOT LIKE '%@example.com');")
    ).scalar() or 0
    assigned_role = "owner" if user_count == 0 else "viewer"

    # 4. Hash password
    hashed_pwd = hash_password(payload.password)

    # 5. Insert into database
    sql = text("""
        INSERT INTO users (username, email, full_name, hashed_password, role, is_active)
        VALUES (:username, :email, :full_name, :hashed_password, :role, TRUE)
        RETURNING id, username, email, full_name, role, is_active, created_at;
    """)

    result = db.execute(
        sql,
        {
            "username": username_clean,
            "email": email_clean,
            "full_name": payload.full_name.strip() if payload.full_name else None,
            "hashed_password": hashed_pwd,
            "role": assigned_role
        }
    )
    user_row = result.mappings().fetchone()

    # 6. Log audit event
    db.execute(
        text("""
            INSERT INTO audit_events (user_id, action, details)
            VALUES (:user_id, 'user_registered', :details);
        """),
        {
            "user_id": user_row["id"],
            "details": f'{{"username": "{username_clean}", "role": "{assigned_role}"}}'
        }
    )
    db.commit()
    return user_row


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user with username (or email) and password.
    Returns a signed JWT access token.
    """
    ident_clean = payload.username.strip().lower()

    # 1. Fetch user by username or email
    sql = text("""
        SELECT id, username, email, full_name, hashed_password, role, is_active, created_at
        FROM users
        WHERE LOWER(username) = :ident OR (email IS NOT NULL AND LOWER(email) = :ident);
    """)
    user = db.execute(sql, {"ident": ident_clean}).mappings().fetchone()

    # 2. Verify existence and password hash
    if not user or not user["hashed_password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    if not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
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
            "username": user["username"],
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
        "username": user["username"],
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


@router.get("/users/search", response_model=List[UserSearchResult])
def search_users(
    q: str = Query(..., min_length=1, max_length=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Searches registered users by username or full name for collaborator invitation recommendations.
    Excludes the currently authenticated user.
    """
    clean_q = q.strip().lower()
    search_term = f"%{clean_q}%"
    sql = text("""
        SELECT id, username, full_name
        FROM users
        WHERE id != :current_user_id
          AND is_active = TRUE
          AND (LOWER(username) LIKE :q OR (full_name IS NOT NULL AND LOWER(full_name) LIKE :q))
        ORDER BY
            CASE WHEN LOWER(username) = :exact THEN 1
                 WHEN LOWER(username) LIKE :start THEN 2
                 ELSE 3 END,
            username ASC
        LIMIT 8;
    """)
    rows = db.execute(sql, {
        "current_user_id": current_user["id"],
        "q": search_term,
        "exact": clean_q,
        "start": f"{clean_q}%"
    }).mappings().fetchall()
    return rows
