"""
Validation utilities for the Travel Customer Management System
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re


def validate_email(email: str) -> bool:
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """Validate phone number (basic validation)"""
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    # Check if it's a reasonable length (7-15 digits)
    return 7 <= len(digits_only) <= 15


def validate_date(date_str: str) -> Optional[datetime]:
    """Validate and parse date string"""
    try:
        # Try different date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y'
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None
    except Exception:
        return None


def validate_travel_dates(departure_date: str, return_date: str) -> Dict[str, Any]:
    """Validate travel dates"""
    errors = []

    dep_date = validate_date(departure_date)
    ret_date = validate_date(return_date)

    if not dep_date:
        errors.append("Invalid departure date format")
    if not ret_date:
        errors.append("Invalid return date format")

    if dep_date and ret_date:
        if ret_date <= dep_date:
            errors.append("Return date must be after departure date")

        # Check if dates are not too far in the future (2 years)
        max_future_date = datetime.now() + timedelta(days=730)
        if dep_date > max_future_date:
            errors.append("Departure date cannot be more than 2 years in the future")

        # Check if departure is not in the past (allow same day)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if dep_date < today:
            errors.append("Departure date cannot be in the past")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "parsed_departure": dep_date.isoformat() if dep_date else None,
        "parsed_return": ret_date.isoformat() if ret_date else None
    }


def validate_travelers_count(count: int) -> bool:
    """Validate number of travelers"""
    return isinstance(count, int) and 1 <= count <= 20


def validate_destination(destination: str) -> bool:
    """Basic validation for destination"""
    if not destination or len(destination.strip()) < 2:
        return False

    # Check for reasonable length
    if len(destination) > 100:
        return False

    # Check for valid characters (letters, spaces, hyphens, apostrophes)
    if not re.match(r"^[a-zA-Z\s\-']+$", destination):
        return False

    return True


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return ""

    # Remove potentially dangerous characters
    # Keep only letters, numbers, spaces, and basic punctuation
    sanitized = re.sub(r'[^\w\s.,!?\-()\']', '', text)

    # Limit length
    return sanitized[:1000]  # Max 1000 characters


def validate_booking_request(booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive validation for booking requests"""
    errors = []
    warnings = []

    # Required fields
    required_fields = ['destination', 'departure_date', 'travelers']
    for field in required_fields:
        if not booking_data.get(field):
            errors.append(f"{field} is required")

    # Validate destination
    if booking_data.get('destination'):
        if not validate_destination(booking_data['destination']):
            errors.append("Invalid destination format")

    # Validate dates
    if booking_data.get('departure_date') and booking_data.get('return_date'):
        date_validation = validate_travel_dates(
            booking_data['departure_date'],
            booking_data['return_date']
        )
        if not date_validation['valid']:
            errors.extend(date_validation['errors'])

    # Validate travelers
    if booking_data.get('travelers'):
        try:
            travelers = int(booking_data['travelers'])
            if not validate_travelers_count(travelers):
                errors.append("Number of travelers must be between 1 and 20")
        except (ValueError, TypeError):
            errors.append("Travelers must be a valid number")

    # Optional validations with warnings
    if booking_data.get('email') and not validate_email(booking_data['email']):
        warnings.append("Email format appears invalid")

    if booking_data.get('phone') and not validate_phone(booking_data['phone']):
        warnings.append("Phone number format appears invalid")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def format_error_message(errors: List[str], warnings: List[str] = None) -> str:
    """Format validation errors and warnings into a user-friendly message"""
    message_parts = []

    if errors:
        message_parts.append("I found some issues with your request:")
        for error in errors:
            message_parts.append(f"• {error}")

    if warnings:
        if errors:
            message_parts.append("\nAdditionally:")
        else:
            message_parts.append("Please note:")

        for warning in warnings:
            message_parts.append(f"• {warning}")

    if errors:
        message_parts.append("\nCould you please correct these issues?")

    return "\n".join(message_parts)