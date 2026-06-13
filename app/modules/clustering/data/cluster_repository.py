from pymongo import ASCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.modules.clustering.domain.models import Cluster, KeywordGroup
from app.modules.clustering.domain.repository import ClusterRepo


class MongoClusterRepository(ClusterRepo):
    """Impl Mongo của ClusterRepo — collections `clusters`/`keyword_groups`,
    và `$set` field cụm ngược về `mentions`. CRUD thuần, không giữ cache
    (cache centroid nằm ở AssignClustersUseCase)."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.clusters = db["clusters"]
        self.keyword_groups = db["keyword_groups"]
        self.mentions = db["mentions"]

    async def ensure_indexes(self) -> None:
        await self.clusters.create_index([("count", ASCENDING)])
        await self.keyword_groups.create_index([("label", ASCENDING)])

    async def load_clusters(self) -> list[Cluster]:
        return [Cluster.model_validate(doc) async for doc in self.clusters.find({})]

    async def load_keyword_groups(self) -> list[KeywordGroup]:
        return [KeywordGroup.model_validate(doc) async for doc in self.keyword_groups.find({})]

    async def upsert_cluster(self, cluster: Cluster) -> None:
        await self.clusters.replace_one({"_id": cluster.id}, cluster.to_mongo(), upsert=True)

    async def upsert_keyword_group(self, group: KeywordGroup) -> None:
        await self.keyword_groups.replace_one({"_id": group.id}, group.to_mongo(), upsert=True)

    async def set_mention_clustering(
        self,
        mention_id: str,
        cluster_id: int,
        cluster_label: str,
        keyword_group_ids: list[int],
    ) -> None:
        await self.mentions.update_one(
            {"_id": mention_id},
            {
                "$set": {
                    "cluster_id": cluster_id,
                    "cluster_label": cluster_label,
                    "keyword_group_ids": keyword_group_ids,
                }
            },
        )
