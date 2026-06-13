"""ABC cho persistence Alert — 2 impl (Mongo trực tiếp / HTTP facade)."""

from abc import ABC, abstractmethod

from app.modules.alerting.domain.models import Alert


class AlertRepository(ABC):
    @abstractmethod
    async def ensure_indexes(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def insert(self, alert: Alert) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_recent(
        self, limit: int = 50, since: str | None = None
    ) -> list[Alert]:
        raise NotImplementedError
