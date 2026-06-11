from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.settings import Settings


class MongoConnection:
    _client: AsyncMongoClient | None = None
    _db: AsyncDatabase | None = None

    @classmethod
    async def connect(cls, settings: Settings) -> AsyncDatabase:
        if cls._client is None:
            cls._client = AsyncMongoClient(settings.mongodb_uri)
            cls._db = cls._client[settings.mongo_db]
            await cls._client.admin.command("ping")
        if cls._db is None:
            cls._db = cls._client[settings.mongo_db]
        return cls._db

    @classmethod
    def get_db(cls) -> AsyncDatabase:
        if cls._db is None:
            raise RuntimeError("MongoDB is not connected")
        return cls._db

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            await cls._client.close()
        cls._client = None
        cls._db = None
