"""Optional LLM adapters; all outputs remain candidates."""
from .providers import BIGMODEL, SILICONFLOW, create_provider, public_catalog
from .secrets import SecretStore
