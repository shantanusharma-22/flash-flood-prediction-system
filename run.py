import os
import sys
import uvicorn

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[STARTUP] NDRF Flash Flood & Landslide Early Warning System listening on http://{host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=False, workers=2)
