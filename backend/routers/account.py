"""Endpoint akun: GET /me — profil user terautentikasi (untuk frontend: tier badge)."""
from fastapi import APIRouter, Depends

from auth import CurrentUser, get_current_user

router = APIRouter(tags=["account"])


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "tier": user.tier}
