"""Builds the configured `StructuredLLM` and describes it for status reporting."""

from app.application.llm import Pricing, StructuredLLM
from app.application.runs.service import ModelInfo
from app.infrastructure.config import Settings
from app.infrastructure.llm.langchain_llm import LangChainStructuredLLM
from app.infrastructure.llm.scripted import ScriptedLLM

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def describe_model(settings: Settings) -> ModelInfo:
    provider = settings.llm_provider
    if provider is None:
        return ModelInfo(False, "none", False, "Set LLM_PROVIDER (google, ollama or scripted)")
    if provider == "scripted":
        return ModelInfo(True, "scripted-demo", True)
    if not settings.llm_model:
        return ModelInfo(False, "none", False, "Set LLM_MODEL")
    if provider == "google" and not settings.llm_api_key_present:
        return ModelInfo(False, settings.llm_model, False, "Set LLM_API_KEY for the Google provider")
    return ModelInfo(True, f"{provider}:{settings.llm_model}", False)


def build_llm(settings: Settings) -> StructuredLLM | None:
    info = describe_model(settings)
    if not info.configured:
        return None
    if settings.llm_provider == "scripted":
        return ScriptedLLM()
    if settings.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.llm_api_key.get_secret_value(),
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
            max_retries=0,  # retries are handled (and bounded) by our adapter
        )
        return _adapter(model, info.name, settings)
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        model = ChatOllama(
            model=settings.llm_model,
            base_url=settings.llm_base_url or DEFAULT_OLLAMA_URL,
            temperature=settings.llm_temperature,
            num_ctx=16_384,  # prompts include generated source files
            num_predict=settings.llm_max_output_tokens,
            reasoning=settings.llm_thinking,
            client_kwargs={"timeout": settings.llm_timeout_seconds},
        )
        return _adapter(model, info.name, settings)
    return None


def _adapter(model, name: str, settings: Settings) -> LangChainStructuredLLM:
    return LangChainStructuredLLM(
        model, name, max_retries=settings.llm_max_retries, budget_seconds=settings.llm_call_budget_seconds
    )


def build_pricing(settings: Settings) -> Pricing | None:
    if settings.llm_provider in ("scripted", "ollama"):
        return Pricing(0.0, 0.0)  # no per-token API charge
    if settings.llm_input_usd_per_mtok is None or settings.llm_output_usd_per_mtok is None:
        return None  # unknown: reported as such, never guessed
    return Pricing(settings.llm_input_usd_per_mtok, settings.llm_output_usd_per_mtok)
