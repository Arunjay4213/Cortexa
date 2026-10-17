from fastapi import APIRouter, Depends, Request
from app.auth import require_auth

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/validate")
async def validate_key(
    request: Request,
    api_key_id: str = Depends(require_auth),
):
    """Validate an API key and return its metadata."""
    if api_key_id == "admin":
        return {"key_id": "admin", "name": "Admin", "key_prefix": "admin"}

    db = getattr(request.app.state, "db", None)
    if db is not None:
        from app.db.tables import api_keys
        from sqlalchemy import select

        async with db() as session:
            result = await session.execute(
                select(api_keys.c.id, api_keys.c.name, api_keys.c.key_prefix).where(
                    api_keys.c.id == api_key_id,
                )
            )
            row = result.first()
            if row:
                return {
                    "key_id": row.id,
                    "name": row.name,
                    "key_prefix": row.key_prefix,
                }

    return {"key_id": api_key_id, "name": "API Key", "key_prefix": "cx_..."}
