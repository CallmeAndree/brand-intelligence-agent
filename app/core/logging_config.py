"""Cấu hình logging dứt khoát cho cả 2 entrypoint uvicorn (app.main, data_backend.main).

Vì sao cần file này: uvicorn tự chạy dictConfig cho riêng các logger `uvicorn*`
(có handler riêng, propagate=False) nhưng KHÔNG gắn handler vào root logger. Một
`logging.basicConfig()` trần ở module app dễ bị no-op hoặc bị uvicorn lấn át, nên
log của worker/use case (LoggerMixin → getLogger("app.modules...")) không chắc ra
stdout — runtime chỉ thấy mỗi access log `GET /health`.

`setup_logging()` ép root logger ghi mọi thứ ra **stdout** ở level lấy từ env
`LOG_LEVEL` (mặc định INFO), rồi cho các logger `uvicorn*` propagate về root để
toàn bộ (app + uvicorn access/error) gom về MỘT luồng thống nhất, đúng kiểu log
container. Gọi ở đầu mỗi entrypoint, sau khi uvicorn đã cấu hình (idempotent).
"""

import logging
import os
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(default_level: str = "INFO") -> None:
    level_name = os.getenv("LOG_LEVEL", default_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    # force=True: xoá mọi handler root sẵn có rồi gắn lại 1 StreamHandler(stdout)
    # → đảm bảo log app luôn ra, không phụ thuộc thứ tự import vs uvicorn.
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format=_FORMAT,
        datefmt=_DATEFMT,
        force=True,
    )

    # Gom log uvicorn về root: bỏ handler riêng + bật propagate → một luồng duy
    # nhất, cùng format/timestamp. (uvicorn.access vẫn in request, gồm /health.)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
        lg.setLevel(level)

    logging.getLogger(__name__).info("Logging đã cấu hình: level=%s, stdout", level_name)
