from openai import AsyncOpenAI

from app.core.settings import Settings, get_settings


def build_embedding_client(settings: Settings | None = None) -> AsyncOpenAI:
    settings = settings or get_settings()
    return AsyncOpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
    )


async def embed_texts(
    client: AsyncOpenAI,
    texts: list[str],
    settings: Settings | None = None,
) -> list[list[float]]:
    settings = settings or get_settings()
    clean_texts = [text.strip() for text in texts]
    if not clean_texts:
        return []

    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=clean_texts,
    )
    vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
    for vector in vectors:
        if len(vector) != settings.embedding_dim:
            raise ValueError(f"Expected {settings.embedding_dim}-dim embedding, got {len(vector)}")
    return vectors
