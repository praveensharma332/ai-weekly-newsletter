from app.providers.base import BaseLLMProvider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider

def get_provider(provider_type: str = "gemini") -> BaseLLMProvider:
    """Helper factory to instantiate the desired LLM provider."""
    provider_type = provider_type.lower()
    if provider_type == "gemini":
        return GeminiProvider()
    elif provider_type == "ollama":
        return OllamaProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")

__all__ = ["BaseLLMProvider", "GeminiProvider", "OllamaProvider", "get_provider"]
