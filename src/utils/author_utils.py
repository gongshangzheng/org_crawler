"""Utility functions for handling author data"""

from typing import Any


def normalize_authors(authors: Any) -> list[str]:
    """
    Normalize authors to a clean list of strings.

    Handles various input formats:
    - List of strings: ["Author One", "Author Two"]
    - Comma-separated string: "Author One, Author Two"
    - List with comma-separated strings: ["Author One, Author Two", "Author Three"]

    Args:
        authors: Authors in various formats (list, string, or other)

    Returns:
        Clean list of author names as strings
    """
    if not isinstance(authors, list):
        if isinstance(authors, str):
            # If comma-separated string, split it
            if ',' in authors:
                return [a.strip() for a in authors.split(',') if a.strip()]
            else:
                return [authors] if authors.strip() else []
        else:
            # Not a list or string, convert to string
            author_str = str(authors).strip()
            return [author_str] if author_str else []

    # Already a list - check for comma-separated strings within
    expanded_authors = []
    for author in authors:
        if isinstance(author, str):
            if ',' in author:
                # Split comma-separated authors
                expanded_authors.extend([a.strip() for a in author.split(',') if a.strip()])
            else:
                if author.strip():
                    expanded_authors.append(author.strip())
        else:
            # Convert non-string to string
            author_str = str(author).strip()
            if author_str:
                expanded_authors.append(author_str)

    return expanded_authors


def format_authors_list(authors: list[str], max_count: int = 3, et_al: bool = True) -> str:
    """
    Format a list of authors for display.

    Args:
        authors: List of author names
        max_count: Maximum number of authors to show before truncating
        et_al: Whether to add "et al." for truncated lists

    Returns:
        Formatted author string
    """
    if not authors:
        return ''

    if len(authors) <= max_count:
        return ', '.join(authors)
    else:
        if et_al:
            return ', '.join(authors[:max_count]) + ' et al.'
        else:
            return ', '.join(authors[:max_count]) + f' ({len(authors)} authors)'
