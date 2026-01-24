"""工具函数模块"""

from .logger import setup_logger, get_logger
from .config_loader import load_global_config, load_rule_config
from .author_utils import normalize_authors, format_authors_list
from .output_format import parse_output_format, should_export_org, should_export_markdown, should_export_json
from .constants import (
    OUTPUT_FORMAT_ORG,
    OUTPUT_FORMAT_MARKDOWN,
    OUTPUT_FORMAT_JSON,
    OUTPUT_FORMAT_BOTH,
    OUTPUT_FORMAT_ALL,
    DEFAULT_AUTHOR_DISPLAY_COUNT,
    DEFAULT_SUMMARY_TRUNCATE_LENGTH,
    DEFAULT_ITEM_PREVIEW_COUNT,
    SECONDS_PER_MINUTE,
    SECONDS_PER_HOUR,
    CHECK_INTERVAL_SECONDS,
)

__all__ = [
    'setup_logger', 'get_logger', 'load_global_config', 'load_rule_config',
    'normalize_authors', 'format_authors_list',
    'parse_output_format', 'should_export_org', 'should_export_markdown', 'should_export_json',
    'OUTPUT_FORMAT_ORG', 'OUTPUT_FORMAT_MARKDOWN', 'OUTPUT_FORMAT_JSON',
    'OUTPUT_FORMAT_BOTH', 'OUTPUT_FORMAT_ALL',
    'DEFAULT_AUTHOR_DISPLAY_COUNT', 'DEFAULT_SUMMARY_TRUNCATE_LENGTH', 'DEFAULT_ITEM_PREVIEW_COUNT',
    'SECONDS_PER_MINUTE', 'SECONDS_PER_HOUR', 'CHECK_INTERVAL_SECONDS',
]

