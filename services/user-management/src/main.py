"""
User Management Service - User authentication, authorization, and profiles
Handles user lifecycle and permission management
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import asyncpg
import os
from passlib.context import CryptContext
from jose import JWTError, jwt

app = FastAPI(title="Trinity User Management Service")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
JWT_SECRET = os.getenv("JWT_SECRET", "trinity-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

pool = None

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None

class UserLogin(BaseModel):
    username: str
    password: str

class User(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    roles: List[str]
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(user_id: int, username: str) -> str:
    expires = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode = {
        "sub": str(user_id),
        "username": username,
        "exp": expires
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return user"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))

        async with pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT id, email, username, full_name, is_active, roles
                FROM users
                WHERE id = $1
            """, user_id)

            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            if not user["is_active"]:
                raise HTTPException(status_code=401, detail="User inactive")

            return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)

    # Create users table
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(200),
                is_active BOOLEAN DEFAULT true,
                roles TEXT[] DEFAULT ARRAY['user'],
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

@app.post("/users/register", response_model=User)
async def register_user(user: UserCreate):
    """Register new user"""

    password_hash = hash_password(user.password)

    try:
        async with pool.acquire() as conn:
            user_id = await conn.fetchval("""
                INSERT INTO users (email, username, password_hash, full_name)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, user.email, user.username, password_hash, user.full_name)

            created_user = await conn.fetchrow("""
                SELECT id, email, username, full_name, is_active, roles, created_at
                FROM users WHERE id = $1
            """, user_id)

            return User(
                id=created_user["id"],
                email=created_user["email"],
                username=created_user["username"],
                full_name=created_user["full_name"],
                is_active=created_user["is_active"],
                roles=created_user["roles"],
                created_at=created_user["created_at"]
            )

    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Email or username already exists")

@app.post("/users/login", response_model=Token)
async def login_user(credentials: UserLogin):
    """Login user and get JWT token"""

    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT id, username, password_hash, is_active
            FROM users
            WHERE username = $1
        """, credentials.username)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user["is_active"]:
            raise HTTPException(status_code=401, detail="User inactive")

        if not verify_password(credentials.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create JWT token
        access_token = create_access_token(user["id"], user["username"])
        expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_at=expires_at
        )

@app.get("/users/me", response_model=User)
async def get_current_user_info(current_user = Depends(get_current_user)):
    """Get current user info"""

    return User(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        is_active=current_user["is_active"],
        roles=current_user["roles"],
        created_at=current_user["created_at"]
    )

@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, update: UserUpdate, current_user = Depends(get_current_user)):
    """Update user (admin only)"""

    # Check if user is admin
    if "admin" not in current_user["roles"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    update_fields = []
    params = []
    param_num = 1

    if update.full_name is not None:
        update_fields.append(f"full_name = ${param_num}")
        params.append(update.full_name)
        param_num += 1

    if update.is_active is not None:
        update_fields.append(f"is_active = ${param_num}")
        params.append(update.is_active)
        param_num += 1

    if update.roles is not None:
        update_fields.append(f"roles = ${param_num}")
        params.append(update.roles)
        param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_fields.append(f"updated_at = NOW()")
    params.append(user_id)

    async with pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE users
            SET {', '.join(update_fields)}
            WHERE id = ${param_num}
        """, *params)

        updated_user = await conn.fetchrow("""
            SELECT id, email, username, full_name, is_active, roles, created_at
            FROM users WHERE id = $1
        """, user_id)

        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found")

        return User(
            id=updated_user["id"],
            email=updated_user["email"],
            username=updated_user["username"],
            full_name=updated_user["full_name"],
            is_active=updated_user["is_active"],
            roles=updated_user["roles"],
            created_at=updated_user["created_at"]
        )

@app.get("/users", response_model=List[User])
async def list_users(current_user = Depends(get_current_user), limit: int = 50):
    """List all users (admin only)"""

    if "admin" not in current_user["roles"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    async with pool.acquire() as conn:
        users = await conn.fetch("""
            SELECT id, email, username, full_name, is_active, roles, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT $1
        """, limit)

        return [
            User(
                id=u["id"],
                email=u["email"],
                username=u["username"],
                full_name=u["full_name"],
                is_active=u["is_active"],
                roles=u["roles"],
                created_at=u["created_at"]
            )
            for u in users
        ]

@app.get("/health")
async def health():
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except:
        return {"status": "unhealthy", "database": "disconnected"}
