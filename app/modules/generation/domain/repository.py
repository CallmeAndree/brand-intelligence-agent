"""ABC cho persistence của MonitorArtifact — 2 impl (Mongo trực tiếp / HTTP facade)."""

from abc import ABC, abstractmethod

from app.modules.generation.domain.models import ArtifactStatus, MonitorArtifact


class MonitorArtifactRepo(ABC):
    @abstractmethod
    async def ensure_indexes(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def insert_draft(self, artifact: MonitorArtifact) -> None:
        """Lưu artifact mới (status=draft). Idempotent theo `_id`."""
        raise NotImplementedError

    @abstractmethod
    async def find_by_cluster(self, cluster_id: int) -> list[MonitorArtifact]:
        """Mọi artifact của một cụm (sắp mới→cũ)."""
        raise NotImplementedError

    @abstractmethod
    async def set_status(self, artifact_id: str, status: ArtifactStatus) -> bool:
        """Đổi vòng đời draft→approved/discarded. True nếu có document khớp."""
        raise NotImplementedError
