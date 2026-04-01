from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/healthz")
async def health(request: Request):
    nli = getattr(request.app.state, "nli", None)
    return {"status": "ok", "model_loaded": nli is not None}
