"""
Minimal dev server for testing auth flow.
Skips NLI model loading — only serves auth + health endpoints.

Usage: CORTEX_ADMIN_SECRET=dev-admin-secret python dev_server.py
"""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

os.environ.setdefault("CORTEX_ADMIN_SECRET", "dev-admin-secret")

from app.config import Settings
from app.routes import auth

settings = Settings()

app = FastAPI(title="CortexOS Dev Server", version="dev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


app.state.settings = settings

if __name__ == "__main__":
    print(f"Admin secret: {settings.admin_secret}")
    print("Dev server starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
