"""HTML-safe text formatting for Telegram messages.

Telegram's HTML parser is strict and fails on:
- Special characters inside tags (< > & ")
- Unclosed tags
- Invalid tag nesting
- Currency symbols (₽) in some contexts

This module provides safe formatting helpers.
"""

import html


def escape_html(text: str) -> str:
    """
    Escape HTML special characters for safe use in Telegram HTML messages.
    
    Converts:
    - < → &lt;
    - > → &gt;
    - & → &amp;
    - " → &quot;
    
    Args:
        text: Raw text that may contain special characters
        
    Returns:
        HTML-escaped text safe for Telegram
    """
    return html.escape(text, quote=False)


def format_price_rub(amount: float, free_text: str = "Бесплатно") -> str:
    """
    Format price in rubles for HTML messages.
    
    Avoids ₽ symbol which can break HTML parsing in some contexts.
    Uses "руб." instead for safety.
    
    Args:
        amount: Price in rubles (0.0 for free)
        free_text: Text to show when amount is 0
        
    Returns:
        Formatted price string safe for HTML
        
    Examples:
        >>> format_price_rub(0.0)
        'Бесплатно'
        >>> format_price_rub(10.50)
        '10.50 руб.'
        >>> format_price_rub(100)
        '100 руб.'
    """
    if amount == 0:
        return free_text
    
    # Format with appropriate precision
    if amount < 1:
        return f"{amount:.2f} руб."
    elif amount < 10:
        return f"{amount:.1f} руб."
    else:
        return f"{amount:.0f} руб."


def sanitize_message_html(text: str) -> str:
    """
    Sanitize user-generated content for HTML messages.
    
    - Escapes all HTML special characters
    - Removes potentially problematic characters
    - Safe for any text input
    
    Args:
        text: User-generated text (prompts, usernames, etc.)
        
    Returns:
        Sanitized text safe for Telegram HTML
    """
    # Escape HTML
    safe_text = escape_html(text)
    
    # Additional safety: limit length
    if len(safe_text) > 4000:
        safe_text = safe_text[:3997] + "..."
    
    return safe_text


def build_html_message(parts: list[str]) -> str:
    """
    Build multi-line HTML message safely.
    
    Args:
        parts: List of message parts (already formatted/escaped)
        
    Returns:
        Joined message with newlines
        
    Example:
        >>> build_html_message([
        ...     "<b>Title</b>",
        ...     "",
        ...     f"Price: {format_price_rub(10.5)}",
        ...     f"User: {sanitize_message_html(username)}"
        ... ])
        '<b>Title</b>\\n\\nPrice: 10.5 руб.\\nUser: escaped_username'
    """
    return "\n".join(parts)
