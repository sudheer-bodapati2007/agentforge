"""Implementations of the `Embedder` port.

  hash    deterministic feature hashing of words, word pairs and character trigrams. No
          model, no network: the default for tests and a working fallback, but it only
          captures shared vocabulary, not meaning.
  ollama  a local embedding model, e.g. nomic-embed-text (which expects task prefixes).
  google  Gemini embeddings (needs LLM_API_KEY).
"""

import hashlib
import math

from app.application.knowledge.ports import EmbeddingError
from app.application.knowledge.search import tokenize
from app.infrastructure.config import Settings

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


class HashEmbedder:
    def __init__(self, dimension: int = 384) -> None:
        self._dimension = dimension

    @property
    def name(self) -> str:
        return f"hash-{self._dimension}"

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        words = tokenize(text)
        features = [(w, 1.0) for w in words] + [(f"{a} {b}", 0.5) for a, b in zip(words, words[1:])]
        features += [(f"#{w[i:i + 3]}", 0.25) for w in words if len(w) > 4 for i in range(len(w) - 2)]
        for feature, weight in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self._dimension
            vector[index] += weight if digest[4] & 1 else -weight
        norm = math.sqrt(sum(x * x for x in vector))
        return [x / norm for x in vector] if norm else vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def _checked(vectors: list[list[float]], expected: int) -> list[list[float]]:
    if len(vectors) != expected or any(not v or any(math.isnan(x) for x in v) for v in vectors):
        raise EmbeddingError("the embedding model returned an unusable response")
    return vectors


class OllamaEmbedder:
    # nomic-embed-text is trained with these prefixes; without them retrieval quality drops.
    _PREFIXES = {"nomic-embed-text": ("search_document: ", "search_query: ")}

    def __init__(self, model: str, base_url: str | None = None, timeout_seconds: int = 120) -> None:
        from langchain_ollama import OllamaEmbeddings

        self._model = model
        self._client = OllamaEmbeddings(
            model=model, base_url=base_url or DEFAULT_OLLAMA_URL, client_kwargs={"timeout": timeout_seconds}
        )
        self._doc_prefix, self._query_prefix = self._PREFIXES.get(model.split(":")[0], ("", ""))

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return _checked(self._client.embed_documents([self._doc_prefix + t for t in texts]), len(texts))
        except EmbeddingError:
            raise
        except Exception as exc:  # connection refused, model not pulled, timeouts
            raise EmbeddingError(f"{self.name}: {str(exc)[:200]}") from exc

    def embed_query(self, text: str) -> list[float]:
        try:
            return _checked([self._client.embed_query(self._query_prefix + text)], 1)[0]
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"{self.name}: {str(exc)[:200]}") from exc


class GoogleEmbedder:
    def __init__(self, model: str, api_key: str) -> None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self._model = model
        self._client = GoogleGenerativeAIEmbeddings(model=model, google_api_key=api_key)

    @property
    def name(self) -> str:
        return f"google:{self._model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return _checked(self._client.embed_documents(texts, task_type="RETRIEVAL_DOCUMENT"), len(texts))
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"{self.name}: {str(exc)[:200]}") from exc

    def embed_query(self, text: str) -> list[float]:
        try:
            return _checked([self._client.embed_query(text, task_type="RETRIEVAL_QUERY")], 1)[0]
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"{self.name}: {str(exc)[:200]}") from exc


def build_embedder(settings: Settings):
    provider = settings.embedding_provider
    if provider == "ollama":
        return OllamaEmbedder(settings.embedding_model or "nomic-embed-text", settings.llm_base_url)
    if provider == "google":
        if not settings.llm_api_key_present:
            raise ValueError("EMBEDDING_PROVIDER=google needs LLM_API_KEY")
        return GoogleEmbedder(settings.embedding_model or "models/gemini-embedding-001", settings.llm_api_key.get_secret_value())
    return HashEmbedder()
