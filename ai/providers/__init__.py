"""
ارائه‌دهندگان هوش مصنوعی.

همه از واسط AIProvider پیروی می‌کنند تا افزودن سرویس جدید بدون تغییر هسته
ممکن باشد (راهنما: docs/ADD_AI_PROVIDER_FA.md).
"""

from ai.providers.base import AIMessage, AIProvider, AIProviderConfig, AIResponse
from ai.providers.catalog import PROVIDER_PRESETS, ProviderPreset, get_preset, preset_keys
from ai.providers.free_models import (
    ModelInfo,
    classify_model,
    free_models,
    known_free_models,
    pick_default_model,
    sort_models,
)
from ai.providers.manager import AIProviderManager
from ai.providers.ollama_provider import OllamaProvider
from ai.providers.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "PROVIDER_PRESETS",
    "ProviderPreset",
    "get_preset",
    "preset_keys",
    "ModelInfo",
    "classify_model",
    "free_models",
    "known_free_models",
    "pick_default_model",
    "sort_models",
    "AIProvider",
    "AIProviderConfig",
    "AIMessage",
    "AIResponse",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "AIProviderManager",
]
