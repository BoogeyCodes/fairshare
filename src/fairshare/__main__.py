"""Run the FairShare server: ``python -m fairshare`` or the ``fairshare`` console script."""

from __future__ import annotations

import os


def run() -> None:
    import uvicorn

    host = os.getenv("FAIRSHARE_HOST", "127.0.0.1")
    port = int(os.getenv("FAIRSHARE_PORT", "8000"))
    uvicorn.run("fairshare.app:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":
    run()
