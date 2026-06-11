from agent_framework_openai import OpenAIChatCompletionClient

from app.core.settings import Settings, get_settings


def build_llm_client(settings: Settings | None = None) -> OpenAIChatCompletionClient:
    settings = settings or get_settings()
    return OpenAIChatCompletionClient(
        model=settings.agent_model,
        api_key=settings.agent_api_key,
        base_url=settings.agent_base_url,
    )
