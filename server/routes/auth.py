"""Auth routes — signup, login, logout, token refresh, account deletion, data export.
No email verification, no OTP, no forgot/reset password."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from schemas import AuthResponse, ChangePasswordRequest
from auth import (
    create_user, authenticate, make_access_token, make_refresh_token,
    decode_token, current_user, current_token_payload, delete_user,
    revoke_token, _is_revoked, EmailAlreadyRegistered,
    hash_password, verify_password, find_user_by_email,
)
from config import MAX_LOGIN_ATTEMPTS
from rate_limit import auth_limit, burst_limit
import db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=10, max_length=500)


def _public_user(user: dict) -> dict:
    return {
        "id": user["_id"],
        "email": user["email"],
        "name": user.get("name", ""),
    }


@router.post("/signup", response_model=AuthResponse)
@auth_limit("5/minute")
async def signup(request: Request, req: SignupRequest) -> AuthResponse:
    try:
        user = await create_user(email=req.email, name=req.name, password=req.password)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in.")
    access_token = make_access_token(user_id=user["_id"], email=user["email"])
    refresh_token = make_refresh_token(user_id=user["_id"], email=user["email"])
    return AuthResponse(token=access_token, refreshToken=refresh_token, user=_public_user(user))


@router.post("/login", response_model=AuthResponse)
@auth_limit("10/minute")
async def login(request: Request, req: LoginRequest) -> AuthResponse:
    failures = await db.get_failed_login_count(req.email)
    if failures >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked after {MAX_LOGIN_ATTEMPTS} failed attempts. Try again in 15 minutes.",
        )
    user = await authenticate(email=req.email, password=req.password)
    if not user:
        await db.record_failed_login(req.email)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    await db.clear_failed_logins(req.email)
    access_token = make_access_token(user_id=user["_id"], email=user["email"])
    refresh_token = make_refresh_token(user_id=user["_id"], email=user["email"])
    return AuthResponse(token=access_token, refreshToken=refresh_token, user=_public_user(user))


@router.post("/refresh", response_model=AuthResponse)
@auth_limit("20/minute")
async def refresh_tokens(request: Request, req: RefreshRequest) -> AuthResponse:
    payload = decode_token(req.refreshToken, expected_type="refresh")
    if await _is_revoked(payload.get("jti")):
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    user = await find_user_by_email(payload["email"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    pwd_changed_at = user.get("passwordChangedAt")
    if pwd_changed_at:
        token_iat = payload.get("iat", 0)
        changed_ts = (
            pwd_changed_at.replace(tzinfo=timezone.utc).timestamp()
            if hasattr(pwd_changed_at, "replace") and pwd_changed_at.tzinfo is None
            else pwd_changed_at.timestamp() if hasattr(pwd_changed_at, "timestamp")
            else float(pwd_changed_at)
        )
        if token_iat < changed_ts:
            raise HTTPException(status_code=401, detail="Session invalidated by a recent password change. Please sign in again.")
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    await revoke_token(payload["jti"], exp)
    new_access = make_access_token(user_id=user["_id"], email=user["email"])
    new_refresh = make_refresh_token(user_id=user["_id"], email=user["email"])
    return AuthResponse(token=new_access, refreshToken=new_refresh, user=_public_user(user))


@router.get("/me")
@burst_limit("60/minute")
async def me(request: Request, user: dict = Depends(current_user)) -> dict:
    return user


@router.post("/logout")
@auth_limit("20/minute")
async def logout(request: Request, payload: dict = Depends(current_token_payload)) -> dict:
    jti = payload.get("jti")
    exp_ts = payload.get("exp")
    if jti and exp_ts:
        expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
        await revoke_token(jti, expires_at)
    return {"ok": True}


@router.delete("/me")
@auth_limit("3/minute")
async def delete_me(request: Request, payload: dict = Depends(current_token_payload)) -> dict:
    user_id = payload["sub"]
    email = payload["email"]
    deleted_messages = await db.delete_messages_for_user(user_id)
    await db.delete_summaries_for_user(user_id)
    await db.delete_session_memory_for_user(user_id)
    await db.delete_goals_for_user(user_id)
    await db.delete_user_memory(user_id)
    await db.delete_feedback_for_user(user_id)
    ok = await delete_user(user_id=user_id, email=email)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found.")
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if payload.get("exp") else None
    if payload.get("jti") and exp:
        await revoke_token(payload["jti"], exp)
    return {"ok": True, "deletedMessages": deleted_messages}


@router.post("/change-password")
@auth_limit("5/minute")
async def change_password(request: Request, req: ChangePasswordRequest, user: dict = Depends(current_user)) -> dict:
    full_user = await find_user_by_email(user["email"])
    if not full_user or not verify_password(req.currentPassword, full_user.get("password", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    new_hash = hash_password(req.newPassword)
    now = datetime.now(timezone.utc)
    if db.is_connected():
        from bson import ObjectId
        from bson.errors import InvalidId
        try:
            oid = ObjectId(user["id"])
        except (InvalidId, TypeError):
            raise HTTPException(status_code=400, detail="Invalid user ID.")
        await db.users().update_one(
            {"_id": oid},
            {"$set": {"password": new_hash, "passwordChangedAt": now}},
        )
    else:
        from auth import _memory_users
        email = user["email"].lower().strip()
        if email in _memory_users:
            _memory_users[email]["password"] = new_hash
            _memory_users[email]["passwordChangedAt"] = now
    return {"ok": True}


@router.get("/export")
@burst_limit("3/minute")
async def export_user_data(request: Request, user: dict = Depends(current_user)):
    from fastapi.responses import Response
    data = await db.export_user_data(user["id"])
    data["exportedAt"] = datetime.now(timezone.utc).isoformat()
    data["email"] = user["email"]
    payload = json.dumps(data, default=str, ensure_ascii=False, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="seelenruh-data-export.json"'},
    )
