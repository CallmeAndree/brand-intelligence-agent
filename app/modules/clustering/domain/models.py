"""Model cho cụm chủ đề (`clusters`) và nhóm từ khóa (`keyword_groups`).

`_id` là `int` (không phải chuỗi như `BaseMongoModel`) để khớp với:
- batch `embed_cluster.py` (id = nhãn cụm dạng int, noise = -1),
- `mention.cluster_id: int | None` và `mention.keyword_group_ids: list[int]`,
- dashboard đọc cùng field.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Cluster(BaseModel):
    id: int = Field(alias="_id")
    label: str
    centroid: list[float]
    count: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    severity_max: int | None = None
    sample_topics: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class KeywordGroup(BaseModel):
    id: int = Field(alias="_id")
    label: str
    keywords: list[str] = Field(default_factory=list)
    centroid: list[float]

    model_config = ConfigDict(populate_by_name=True)

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)
