"""Errors and Warnings."""


class OSTAuthenticationError(ValueError):
    """Raised when a somwthing is wrong with your credentials."""


class OSTConfigError(ValueError):
    """Raised when a OST process configuration is invalid."""


class GPTRuntimeError(RuntimeError):
    """Raised when a GPT process returns wrong return code."""


class EmptyInventoryException(ValueError):
    """Raised when a Inventory is empty when it shouldn't."""


class EmptySearchError(ValueError):
    """Raised when a Search returns empty when it probably shouldn't."""


class SceneNotDownloadedException(ValueError):
    """Raised when a Scene should have been downloaded beforehand."""
