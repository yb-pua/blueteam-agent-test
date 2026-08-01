from abc import ABC, abstractmethod
from typing import ClassVar


class OSINTSource(ABC):
    name: str = ""
    supported_types: ClassVar[list[str]] = []
    requires_key: bool = False
    is_configured: bool = False

    def __init__(self):
        self._check_config()

    def _check_config(self):
        pass

    def reload(self) -> bool:
        """Re-check configuration. Returns True if configured state changed."""
        old = self.is_configured
        self._check_config()
        return self.is_configured != old

    @abstractmethod
    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        ...

    def can_handle(self, ioc_type: str) -> bool:
        return ioc_type in self.supported_types
