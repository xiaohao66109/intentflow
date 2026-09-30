"""Deterministic provider used only by automated tests."""
from .base import ProviderIdentity, SuggestionProvider

class MockSuggestionProvider(SuggestionProvider):
    def __init__(self, outputs, model="mock-structured"):
        self.outputs = outputs
        self.identity = ProviderIdentity("mock", model)

    def test_connection(self):
        return {"ok": True, "provider": "mock", "model": self.identity.model}

    def suggest(self, skill, inputs):
        value = self.outputs[skill["id"]]
        return dict(value), "Deterministic test candidate"
