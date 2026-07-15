"""Auth endpoints: signup, login, me, delete account, logout, change-password,
forgot-password, reset-password, verify-email, resend-verification, data-export."""
import asyncio
import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from schemas import SignupRequest, LoginRequest, AuthResponse, ChangePasswordRequest
from auth import (
    create_user,
    authenticate,
    make_access_token,
    make_refresh_token,
    decode_token,
    current_user,
    current_token_payload,
    delete_user,
    revoke_token,
    _is_revoked,
    EmailAlreadyRegistered,
    hash_password,
    verify_password,
    find_user_by_email,
)
from config import MAX_LOGIN_ATTEMPTS
from rate_limit import auth_limit, burst_limit
import db
import mailer

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _public_user(user: dict) -> dict:
    return {"id": user["_id"], "email": user["email"], "name": user.get("name", "")}


@router.post("/signup", response_model=AuthResponse)
@auth_limit("5/minute")
async def signup(request: Request, req: SignupRequest) -> AuthResponse:
    try:
        user = await create_user(email=req.email, name=req.name, password=req.password)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=400, detail="Couldn't create that account. Please try again.")
    access_token = make_access_token(user_id=user["_id"], email=user["email"])
    refresh_token = make_refresh_token(user_id=user["_id"], email=user["email"])
    # Send email verification — fire-and-forget so signup isn't delayed
    verification_token = secrets.token_urlsafe(32)
    await db.save_verification_token(email=user["email"], token=verification_token)
    asyncio.create_task(mailer.send_email_verification(to=user["email"], token=verification_token))
    return AuthResponse(token=access_token, refreshToken=refresh_token, user=_public_user(user))


@router.post("/login", response_model=AuthResponse)
@auth_limit("10/minute")
async def login(request: Request, req: LoginRequest) -> AuthResponse:
    # Check lockout before running bcrypt (avoids timing leak on locked accounts)
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
    # Success — clear failure counter and issue both tokens
    await db.clear_failed_logins(req.email)
    access_token = make_access_token(user_id=user["_id"], email=user["email"])
    refresh_token = make_refresh_token(user_id=user["_id"], email=user["email"])
    return AuthResponse(token=access_token, refreshToken=refresh_token, user=_public_user(user))


@router.get("/me")
@burst_limit("60/minute")
async def me(request: Request, user: dict = Depends(current_user)) -> dict:
    return user


@router.delete("/me")
@auth_limit("3/minute")
async def delete_me(request: Request, payload: dict = Depends(current_token_payload)) -> dict:
    """Delete the caller's account and all associated data."""
    user_id = payload["sub"]
    email = payload["email"]
    # Wipe every message owned by this user, not just the default session.
    deleted_messages = await db.delete_messages_for_user(user_id)
    await db.delete_summaries_for_user(user_id)
    await db.delete_session_memory_for_user(user_id)
    await db.delete_goals_for_user(user_id)
    await db.delete_user_memory(user_id)
    await db.delete_feedback_for_user(user_id)
    ok = await delete_user(user_id=user_id, email=email)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found.")
    # Revoke this token so the soon-to-be-cleared client can't be reused.
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if payload.get("exp") else None
    if payload.get("jti") and exp:
        await revoke_token(payload["jti"], exp)
    return {"ok": True, "deletedMessages": deleted_messages}


@router.post("/change-password")
@auth_limit("5/minute")
async def change_password(request: Request, req: ChangePasswordRequest, user: dict = Depends(current_user)) -> dict:
    """Change password. Invalidates all existing refresh tokens issued before this moment."""
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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
@auth_limit("5/minute")
async def forgot_password(request: Request, req: ForgotPasswordRequest) -> dict:
    """Generate a password-reset token and email it (or log it in dev mode).
    Always returns 200 so attackers cannot enumerate registered emails."""
    user = await find_user_by_email(req.email)
    if user:
        token = secrets.token_urlsafe(32)
        await db.save_reset_token(email=user["email"], token=token)
        asyncio.create_task(mailer.send_password_reset(to=user["email"], token=token))
    return {"ok": True, "message": "If that email is registered, a reset link has been sent."}


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    newPassword: str = Field(min_length=6, max_length=128)


@router.post("/reset-password")
@auth_limit("10/minute")
async def reset_password(request: Request, req: ResetPasswordRequest) -> dict:
    """Consume a password-reset token and update the user's password."""
    email = await db.consume_reset_token(token=req.token)
    if not email:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")
    new_hash = hash_password(req.newPassword)
    if db.is_connected():
        await db.users().update_one(
            {"email": email.lower().strip()},
            {"$set": {"password": new_hash}},
        )
    else:
        from auth import _memory_users
        key = email.lower().strip()
        if key in _memory_users:
            _memory_users[key]["password"] = new_hash
    return {"ok": True}


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/verify-email")
@auth_limit("10/minute")
async def verify_email(request: Request, req: VerifyEmailRequest) -> dict:
    """Mark the user's email as verified by consuming the verification token."""
    email = await db.consume_verification_token(token=req.token)
    if not email:
        raise HTTPException(status_code=400, detail="Verification link is invalid or has expired.")
    await db.mark_email_verified(email)
    return {"ok": True, "email": email}


@router.post("/resend-verification")
@auth_limit("3/minute")
async def resend_verification(request: Request, user: dict = Depends(current_user)) -> dict:
    """Re-send the email verification link for the currently signed-in user."""
    token = secrets.token_urlsafe(32)
    await db.save_verification_token(email=user["email"], token=token)
    asyncio.create_task(mailer.send_email_verification(to=user["email"], token=token))
    return {"ok": True}


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=10, max_length=500)


@router.post("/refresh", response_model=AuthResponse)
@auth_limit("20/minute")
async def refresh_tokens(request: Request, req: RefreshRequest) -> AuthResponse:
    """Issue new access + refresh tokens. Old refresh token is revoked on use."""
    payload = decode_token(req.refreshToken, expected_type="refresh")
    if await _is_revoked(payload.get("jti")):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked. Please sign in again.")
    user = await find_user_by_email(payload["email"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    # Reject tokens issued before a password change — this is how all devices
    # are signed out when the user changes their password.
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
            raise HTTPException(
                status_code=401,
                detail="Session invalidated by a recent password change. Please sign in again.",
            )

    # Rotate: revoke old refresh token so it can't be reused
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    await revoke_token(payload["jti"], exp)
    new_access = make_access_token(user_id=user["_id"], email=user["email"])
    new_refresh = make_refresh_token(user_id=user["_id"], email=user["email"])
    return AuthResponse(token=new_access, refreshToken=new_refresh, user=_public_user(user))


@router.get("/export")
@burst_limit("3/minute")
async def export_user_data(request: Request, user: dict = Depends(current_user)):
    """Download everything stored about the authenticated user as JSON."""
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


@router.post("/logout")
@auth_limit("20/minute")
async def logout(request: Request, payload: dict = Depends(current_token_payload)) -> dict:
    """Revoke the caller's JWT. Idempotent — safe to call twice."""
    jti = payload.get("jti")
    exp_ts = payload.get("exp")
    if not jti or not exp_ts:
        # Legacy tokens without a jti can't be individually revoked;
        # the client will still clear them locally.
        return {"ok": True, "revoked": False, "reason": "Token missing jti — relying on client-side clear."}
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    await revoke_token(jti, expires_at)
    return {"ok": True, "revoked": True}
