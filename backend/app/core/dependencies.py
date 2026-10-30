from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {
    "viewer": 1,
    "editor": 2,
    "owner": 3
}


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency that enforces authentication.
    Validates JWT token and fetches active user from PostgreSQL.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload["sub"])
    sql = text("""
        SELECT id, email, full_name, role, is_active, created_at
        FROM users
        WHERE id = :user_id AND is_active = TRUE;
    """)
    user = db.execute(sql, {"user_id": user_id}).mappings().fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dict(user)


def get_project_member_role(project_id: int, user_id: int, db: Session) -> Optional[str]:
    """
    Queries PostgreSQL to find the user's role in a given project.
    Checks both project_members and projects.owner_id.
    """
    sql = text("""
        SELECT pm.role
        FROM project_members pm
        WHERE pm.project_id = :project_id AND pm.user_id = :user_id
        UNION
        SELECT 'owner' AS role
        FROM projects p
        WHERE p.id = :project_id AND p.owner_id = :user_id;
    """)
    rows = db.execute(sql, {"project_id": project_id, "user_id": user_id}).fetchall()
    if not rows:
        return None

    # Return highest role found
    roles = [r[0] for r in rows if r[0] in ROLE_HIERARCHY]
    if not roles:
        return None
    return max(roles, key=lambda r: ROLE_HIERARCHY.get(r, 0))


def require_project_permission(
    project_id: int,
    required_role: str = "viewer",
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Enforces that the current authenticated user has at least the required role
    (viewer, editor, owner) for the specified project.
    """
    # System administrator / owner has universal access
    if current_user.get("role") == "owner":
        return current_user

    role = get_project_member_role(project_id, current_user["id"], db)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. You are not a member of project #{project_id}."
        )

    required_level = ROLE_HIERARCHY.get(required_role, 1)
    actual_level = ROLE_HIERARCHY.get(role, 0)

    if actual_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Role '{required_role}' required, but you are '{role}'."
        )

    return current_user
