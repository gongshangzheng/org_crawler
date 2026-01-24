"""Utility functions for handling output format configuration"""

from typing import Any
from .constants import (
    OUTPUT_FORMAT_ORG,
    OUTPUT_FORMAT_MARKDOWN,
    OUTPUT_FORMAT_JSON,
    OUTPUT_FORMAT_BOTH,
    OUTPUT_FORMAT_ALL
)


def parse_output_format(config: Any) -> list[str]:
    """
    Parse output format configuration into a list of formats.

    Supports various input formats:
    - String: 'org', 'markdown', 'json', 'both', 'all'
    - List: ['org', 'markdown'], ['org', 'json']
    - Comma-separated string: 'org,markdown', 'org,json'

    Args:
        config: Output format configuration from YAML

    Returns:
        List of format strings (e.g., ['org', 'markdown'])
    """
    # Handle None case
    if config is None:
        return [OUTPUT_FORMAT_ORG]

    # Handle string input
    if isinstance(config, str):
        config_lower = config.lower()
        if config_lower == OUTPUT_FORMAT_BOTH:
            return [OUTPUT_FORMAT_ORG, OUTPUT_FORMAT_MARKDOWN]
        elif config_lower == OUTPUT_FORMAT_ALL:
            return [OUTPUT_FORMAT_ORG, OUTPUT_FORMAT_MARKDOWN, OUTPUT_FORMAT_JSON]
        elif ',' in config:
            # Comma-separated string
            return [f.strip().lower() for f in config.split(',')]
        else:
            # Single format
            return [config_lower]

    # Handle list input
    if isinstance(config, list):
        return [f.lower() if isinstance(f, str) else str(f).lower() for f in config]

    # Default fallback
    return [OUTPUT_FORMAT_ORG]


def should_export_org(formats: list[str]) -> bool:
    """Check if org format should be exported"""
    return OUTPUT_FORMAT_ORG in formats


def should_export_markdown(formats: list[str]) -> bool:
    """Check if markdown format should be exported"""
    return OUTPUT_FORMAT_MARKDOWN in formats


def should_export_json(formats: list[str]) -> bool:
    """Check if json format should be exported"""
    return OUTPUT_FORMAT_JSON in formats
