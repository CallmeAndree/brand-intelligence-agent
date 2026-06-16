"""EmailSender — gửi email alert qua SMTP Gmail (STARTTLS).

Cấu hình từ env: user=`SEND_EMAIL`, pass=`EMAIL_APP_PASSWORD`, to=`RECEIVE_EMAIL`,
host/port `SMTP_HOST`/`SMTP_PORT`. Thiếu cấu hình → trả status "skipped" (không lỗi);
gửi lỗi → "failed" + error. Gửi thật KHÔNG cần duyệt từng lần (user đã ủy quyền bền).

`smtplib` là blocking → chạy trong thread (asyncio.to_thread) để không nghẽn event loop.
"""

import asyncio
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from app.core.logging_mixin import LoggerMixin
from app.core.settings import Settings
from app.modules.alerting.domain.models import AlertEmail, EmailStatus

# Render markdown brief thành HTML tối giản nếu có thư viện; fallback text thuần.
try:
    from markdown import markdown as _md_to_html  # type: ignore
except Exception:  # noqa: BLE001
    _md_to_html = None


class EmailSender(LoggerMixin):
    def __init__(self, settings: Settings) -> None:
        self._user = settings.send_email
        self._password = settings.email_app_password
        self._to = settings.receive_email
        self._host = settings.smtp_host
        self._port = settings.smtp_port

    @property
    def smtp_ready(self) -> bool:
        return bool(self._user and self._password)

    async def send(self, subject: str, body_md: str, to: str | None = None) -> AlertEmail:
        # `to` = email phòng ban (điều phối); thiếu → fallback hộp chung RECEIVE_EMAIL.
        recipient = (to or self._to or "").strip()
        if not self.smtp_ready or not recipient:
            self.logger.info("SMTP/recipient chưa cấu hình — bỏ qua gửi email (skipped)")
            return AlertEmail(to=recipient or None, subject=subject, status=EmailStatus.SKIPPED)
        try:
            await asyncio.to_thread(self._send_sync, subject, body_md, recipient)
            return AlertEmail(
                to=recipient,
                subject=subject,
                status=EmailStatus.SENT,
                sent_at=datetime.now(timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001
            self.log_exception("Gửi email alert thất bại")
            return AlertEmail(
                to=recipient,
                subject=subject,
                status=EmailStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}"[:500],
            )

    def _send_sync(self, subject: str, body_md: str, recipient: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._user
        msg["To"] = recipient
        msg.set_content(body_md)
        if _md_to_html is not None:
            msg.add_alternative(_md_to_html(body_md), subtype="html")
        with smtplib.SMTP(self._host, self._port, timeout=30) as server:
            server.starttls()
            server.login(self._user, self._password)
            server.send_message(msg)
