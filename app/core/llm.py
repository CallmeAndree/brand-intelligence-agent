from agent_framework_openai import OpenAIChatCompletionClient

from app.core.settings import Settings, get_settings


def _build(settings: Settings, model: str) -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model,
        api_key=settings.api_key,
        base_url=settings.base_url,
    )


def build_gemma_client(settings: Settings | None = None) -> OpenAIChatCompletionClient:
    """Client GEMMA — tác vụ phân loại/trích xuất volume cao: enrich + đặt nhãn cụm."""
    settings = settings or get_settings()
    return _build(settings, settings.gemma_model)


def build_minimax_client(settings: Settings | None = None) -> OpenAIChatCompletionClient:
    """Client MINIMAX — sinh text chất lượng: 5 tính năng monitor (bắt buộc) + alert brief."""
    settings = settings or get_settings()
    return _build(settings, settings.minimax_model)
