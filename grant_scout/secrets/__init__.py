"""Secret handling for auto-apply.

The contract: secret VALUES live only here and only flow to the browser via the
deterministic injection path. They never enter the LLM's context, argv, logs, or
screenshots. The `resolver` is the sole reader of the `vault`.
"""

from .vault import Vault, InMemoryBackend, KeyringBackend
from .registry import Registry
from .resolver import Resolver, mask

__all__ = ["Vault", "InMemoryBackend", "KeyringBackend", "Registry", "Resolver", "mask"]
