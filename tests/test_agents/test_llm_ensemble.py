from __future__ import annotations

from aria.engine.ensemble.agent import LLMEnsembleAgent
from aria.engine.memory.shared_memory import SharedMemory


class _DummyLogger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None


class _DummyCleaner:
    async def call_llm_async(self, *_args, **_kwargs):
        return None

    def parse_json_payload(self, *_args, **_kwargs):
        return None


class _Settings:
    llm_provider = "ollama"
    ollama_model = "llama3.1:8b"
    ensemble_max_tokens = 1500
    ensemble_temperature = 0.3
    ensemble_timeout = 60
    ensemble_min_response_words = 50


async def _noop_emit(*_args, **_kwargs):
    return None


async def _noop_persist(*_args, **_kwargs):
    return None


def _noop_metric(*_args, **_kwargs):
    return None


def test_cleaning_brain_is_excluded_from_ensemble_models():
    mission = {
        "llm_sources": {
            "enabled": True,
            "models": [
                {"provider": "ollama", "model_id": "llama3.1:8b", "enabled": True},
                {"provider": "ollama", "model_id": "mistral", "enabled": True},
            ],
            "query_settings": {},
            "comparison": {},
        }
    }
    agent = LLMEnsembleAgent(
        mission=mission,
        shared_memory=SharedMemory(),
        settings=_Settings(),
        logger=_DummyLogger(),
        cleaner=_DummyCleaner(),
        persist_document=_noop_persist,
        emit=_noop_emit,
        record_metric=_noop_metric,
    )
    assert [model["model_id"] for model in agent.enabled_models] == ["mistral"]
