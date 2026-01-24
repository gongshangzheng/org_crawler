"""Constants for the crawler application"""

# Output format types
OUTPUT_FORMAT_ORG = 'org'
OUTPUT_FORMAT_MARKDOWN = 'markdown'
OUTPUT_FORMAT_JSON = 'json'

# Output format aliases
OUTPUT_FORMAT_BOTH = 'both'      # org + markdown
OUTPUT_FORMAT_ALL = 'all'        # org + markdown + json

# Display limits
DEFAULT_AUTHOR_DISPLAY_COUNT = 3
DEFAULT_SUMMARY_TRUNCATE_LENGTH = 200
DEFAULT_ITEM_PREVIEW_COUNT = 3

# Time constants
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
CHECK_INTERVAL_SECONDS = 60
