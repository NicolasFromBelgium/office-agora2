"""Entry point: python -m agora starts the web app."""

from __future__ import annotations

import uvicorn

from agora.settings import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "agora.web.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development" and settings.debug,
        log_level=settings.log_level,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1,::1",
    )


if __name__ == "__main__":
    main()
