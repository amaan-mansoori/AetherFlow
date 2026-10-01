"""Executable entrypoint for the FastAPI API process."""

import uvicorn

from aetherflow.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "aetherflow.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
