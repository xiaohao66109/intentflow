"""Configurable provider registry."""
from .openai_compatible import OpenAICompatibleProvider

SILICONFLOW = {
    "id": "siliconflow",
    "name": "SiliconFlow",
    "endpoint": "https://api.siliconflow.cn/v1/chat/completions",
    # Current free choices are configuration defaults, not a permanent platform guarantee.
    "models": ["THUDM/GLM-4-9B-0414", "Qwen/Qwen3.5-4B"],
    "default_model": "THUDM/GLM-4-9B-0414",
}

BIGMODEL = {
    "id": "bigmodel",
    "name": "智谱 BigModel",
    "endpoint": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "models": ["glm-4-flash-250414", "glm-4-flashx-250414"],
    "default_model": "glm-4-flash-250414",
}

PROVIDERS = {"bigmodel": BIGMODEL, "siliconflow": SILICONFLOW}

def public_catalog():
    return [{key: value for key, value in provider.items() if key != "endpoint"}
            for provider in (BIGMODEL, SILICONFLOW)]

def create_provider(config, secret_store, client=None):
    provider_id = config.get("provider")
    if provider_id not in PROVIDERS:
        raise ValueError("Unsupported AI provider")
    provider = PROVIDERS[provider_id]
    model = str(config.get("model", "")).strip()
    if not model or len(model) > 200:
        raise ValueError("A configurable model_id is required")
    key = secret_store.get(config.get("credential_ref"))
    return OpenAICompatibleProvider(provider_id, provider["endpoint"], model, key, client)
