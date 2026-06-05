"""Windows 개발용 서버 실행 wrapper.

uvicorn cli는 OS 기본 event loop을 따라가서(Windows = ProactorEventLoop) psycopg async와
호환 안 됨. `asyncio.run(loop_factory=...)`로 SelectorEventLoop을 강제한 다음 그 안에서
uvicorn.Server.serve()를 실행.

Linux/Mac은 영향 없음 — 운영 배포(`uvicorn main:app`)와는 별개 dev wrapper.
"""

import asyncio
import os
import selectors
import sys

import uvicorn


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    config = uvicorn.Config(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(config)

    if sys.platform == "win32":
        # SelectorEventLoop으로 강제 — psycopg async 호환.
        asyncio.run(
            server.serve(),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
