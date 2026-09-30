"""Provider interface. Providers return candidates and never write Core objects."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderIdentity:
    provider: str
    model: str

class SuggestionProvider(ABC):
    identity: ProviderIdentity

    @abstractmethod
    def test_connection(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def suggest(self, skill: dict, inputs: dict) -> tuple[dict, str]:
        raise NotImplementedError
