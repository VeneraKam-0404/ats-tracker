#!/usr/bin/env python3
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    reload = os.environ.get("ATS_RELOAD", "true").lower() == "true"
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)
