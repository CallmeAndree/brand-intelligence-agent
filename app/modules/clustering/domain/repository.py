from abc import ABC, abstractmethod

from app.modules.clustering.domain.models import Cluster, KeywordGroup


class ClusterRepo(ABC):
    """Persistence cho cụm chủ đề + nhóm từ khóa. CRUD thuần (stateless);
    cache centroid in-memory do `AssignClustersUseCase` giữ (xem spec)."""

    @abstractmethod
    async def ensure_indexes(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def load_clusters(self) -> list[Cluster]:
        raise NotImplementedError

    @abstractmethod
    async def load_keyword_groups(self) -> list[KeywordGroup]:
        raise NotImplementedError

    @abstractmethod
    async def upsert_cluster(self, cluster: Cluster) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_keyword_group(self, group: KeywordGroup) -> None:
        raise NotImplementedError

    @abstractmethod
    async def set_mention_clustering(
        self,
        mention_id: str,
        cluster_id: int,
        cluster_label: str,
        keyword_group_ids: list[int],
    ) -> None:
        raise NotImplementedError
