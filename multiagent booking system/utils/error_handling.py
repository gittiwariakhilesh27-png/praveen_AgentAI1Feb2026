"""
Error handling utilities for the Travel Customer Management System
"""

from typing import Dict, Any, Optional, Callable
from functools import wraps
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TravelAgentError(Exception):
    """Base exception for travel agent errors"""

    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class ValidationError(TravelAgentError):
    """Validation-related errors"""
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(
            message,
            "VALIDATION_ERROR",
            {"field": field, "value": str(value) if value is not None else None}
        )


class BookingError(TravelAgentError):
    """Booking-related errors"""
    def __init__(self, message: str, booking_id: str = None):
        super().__init__(
            message,
            "BOOKING_ERROR",
            {"booking_id": booking_id}
        )


class APIError(TravelAgentError):
    """External API-related errors"""
    def __init__(self, message: str, service: str, status_code: int = None):
        super().__init__(
            message,
            "API_ERROR",
            {"service": service, "status_code": status_code}
        )


class ConfigurationError(TravelAgentError):
    """Configuration-related errors"""
    def __init__(self, message: str, config_key: str = None):
        super().__init__(
            message,
            "CONFIGURATION_ERROR",
            {"config_key": config_key}
        )


def handle_agent_errors(func: Callable) -> Callable:
    """Decorator to handle errors in agent methods"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Validation error in {func.__name__}: {e.message}")
            return _handle_validation_error(e, args[0] if args else None)
        except APIError as e:
            logger.error(f"API error in {func.__name__}: {e.message}")
            return _handle_api_error(e, args[0] if args else None)
        except BookingError as e:
            logger.error(f"Booking error in {func.__name__}: {e.message}")
            return _handle_booking_error(e, args[0] if args else None)
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            logger.error(traceback.format_exc())
            return _handle_unexpected_error(e, args[0] if args else None)

    return wrapper


def _handle_validation_error(error: ValidationError, state: Any = None) -> Any:
    """Handle validation errors"""
    from graph import add_message_to_state

    error_message = f"I apologize, but there's an issue with the information provided: {error.message}"

    if error.details.get("field"):
        error_message += f" Please check the {error.details['field']} field."

    if state:
        return add_message_to_state(
            state,
            "agent",
            error_message,
            "error_handler"
        )

    return {"error": error_message}


def _handle_api_error(error: APIError, state: Any = None) -> Any:
    """Handle API-related errors"""
    from graph import add_message_to_state

    service = error.details.get("service", "external service")

    error_message = f"I'm experiencing technical difficulties connecting to {service}. Please try again in a few moments, or contact customer support if the issue persists."

    if state:
        return add_message_to_state(
            state,
            "agent",
            error_message,
            "error_handler"
        )

    return {"error": error_message}


def _handle_booking_error(error: BookingError, state: Any = None) -> Any:
    """Handle booking-related errors"""
    from graph import add_message_to_state

    booking_id = error.details.get("booking_id", "")
    if booking_id:
        error_message = f"There was an issue with booking {booking_id}: {error.message}"
    else:
        error_message = f"There was an issue processing your booking: {error.message}"

    error_message += " Our team has been notified and will assist you shortly."

    if state:
        return add_message_to_state(
            state,
            "agent",
            error_message,
            "error_handler"
        )

    return {"error": error_message}


def _handle_unexpected_error(error: Exception, state: Any = None) -> Any:
    """Handle unexpected errors"""
    from graph import add_message_to_state

    error_message = "I apologize, but I'm experiencing an unexpected technical issue. Our support team has been notified. Please try again in a few minutes or contact customer support for immediate assistance."

    if state:
        return add_message_to_state(
            state,
            "agent",
            error_message,
            "error_handler"
        )

    return {"error": error_message}


def safe_api_call(func: Callable, *args, service_name: str = "external service", **kwargs) -> Any:
    """Safely call external API functions with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"API call to {service_name} failed: {e}")
        raise APIError(
            f"Failed to connect to {service_name}",
            service=service_name
        ) from e


def validate_and_sanitize_input(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize input data"""
    from .validation import sanitize_input, validate_booking_request

    sanitized = {}

    for key, value in input_data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_input(value)
        else:
            sanitized[key] = value

    # If this looks like booking data, validate it
    if any(field in sanitized for field in ['destination', 'departure_date', 'travelers']):
        validation_result = validate_booking_request(sanitized)
        if not validation_result['valid']:
            raise ValidationError(
                f"Invalid booking data: {', '.join(validation_result['errors'])}"
            )

    return sanitized


class ErrorRecovery:
    """Error recovery strategies"""

    @staticmethod
    def retry_with_backoff(func: Callable, max_retries: int = 3, backoff_factor: float = 2.0):
        """Retry a function with exponential backoff"""
        import time

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e

                wait_time = backoff_factor ** attempt
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)

    @staticmethod
    def fallback_response(error: Exception, fallback_message: str = None) -> str:
        """Provide fallback response when all else fails"""
        if fallback_message:
            return fallback_message

        return "I'm currently experiencing technical difficulties. Please try again later or contact our customer support team for immediate assistance."

    @staticmethod
    def log_error_for_support(error: TravelAgentError, context: Dict[str, Any] = None):
        """Log error details for support team review"""
        error_details = {
            "error_type": type(error).__name__,
            "error_code": error.error_code,
            "message": error.message,
            "details": error.details,
            "timestamp": error.timestamp.isoformat(),
            "context": context or {}
        }

        logger.error(f"Support Error Log: {error_details}")

        # In a production system, you might want to:
        # - Send to error monitoring service (Sentry, Rollbar, etc.)
        # - Store in database for support review
        # - Send email alert to support team