import os

import uvicorn

if __name__ == "__main__":
    # Render (and other PaaS hosts) assign the port via $PORT; default to
    # 8000 for local runs. A hardcoded port fails the host health check.
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
