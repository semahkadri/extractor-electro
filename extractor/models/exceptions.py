class GeminiExtractorError(Exception):
    """Base exception for all extractor errors."""


class ApiKeyError(GeminiExtractorError):
    """No valid API key found."""


class RateLimitError(GeminiExtractorError):
    """API key or model hit its rate limit."""

    def __init__(self, message: str, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AllModelsExhaustedError(GeminiExtractorError):
    """Every model in the fallback chain is rate-limited."""


class ExtractionError(GeminiExtractorError):
    """Response could not be parsed into valid data."""


class ImageError(GeminiExtractorError):
    """Input image could not be loaded or processed."""
