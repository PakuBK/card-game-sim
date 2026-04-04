from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    # Simple local dev launcher for the FastAPI app.
    uvicorn.run(
        "app.main:app",
        host=os.getenv("BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=True,
    )
