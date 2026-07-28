"""Custom exceptions for AI-backed services."""


class AIServiceError(Exception):
    """Raised when an external AI provider fails or returns an unusable response.

    Attributes:
        user_message: Friendly text safe to show in the UI.
        technical_detail: Provider/raw detail for logs and the browser console.
    """

    def __init__(self, message: str, *, technical_detail: str | None = None) -> None:
        """Create an AI service failure with optional technical detail.

        Args:
            message: User-facing explanation of the failure.
            technical_detail: Raw/provider detail for debugging. Defaults to ``message``.
        """
        super().__init__(message)
        self.user_message = message
        self.technical_detail = technical_detail or message
