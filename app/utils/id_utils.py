"""
Utilities for generating and validating nanoid-based identifiers.
"""
from nanoid import generate


def generate_id(size: int = 21) -> str:
    """
    Generate a nanoid string.
    
    Args:
        size: Length of the generated ID. Default is 21 characters.
    
    Returns:
        A URL-safe nanoid string.
    """
    return generate(size=size)


def generate_short_id(size: int = 12) -> str:
    """
    Generate a shorter nanoid string for use cases where space is limited.
    
    Args:
        size: Length of the generated ID. Default is 12 characters.
    
    Returns:
        A URL-safe nanoid string.
    """
    return generate(size=size)


def is_valid_nanoid(id_string: str, expected_size: int = 21) -> bool:
    """
    Validate if a string is a valid nanoid format.
    
    Args:
        id_string: The string to validate.
        expected_size: Expected length of the nanoid. Default is 21.
    
    Returns:
        True if the string is a valid nanoid format, False otherwise.
    """
    if not isinstance(id_string, str):
        return False
    
    if len(id_string) != expected_size:
        return False
    
    # nanoid uses URL-safe characters: A-Z, a-z, 0-9, _, -
    allowed_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-')
    return all(char in allowed_chars for char in id_string)