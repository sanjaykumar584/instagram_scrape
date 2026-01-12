"""
Dynamic HTTP header generation with randomization.
Generates realistic, varied headers to avoid fingerprinting detection.
"""

import random
from typing import Dict, List
from user_agent_pool import get_user_agent_with_headers
from logger_config import get_logger

logger = get_logger("header_generator")

# Language preference pools
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,es;q=0.8",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.9,fr;q=0.8",
    "en-US,en;q=0.9,de;q=0.8",
    "en-US,en;q=0.9,ja;q=0.8",
    "en-US,en;q=0.9,zh-CN;q=0.8",
    "en-GB,en-US;q=0.9,en;q=0.8",
]

# Accept encodings (varied order)
ACCEPT_ENCODINGS = [
    "gzip, deflate, br",
    "gzip, deflate, br, zstd",
    "gzip, deflate",
    "br, gzip, deflate",
]

# Accept header variations
ACCEPT_HEADERS = [
    "*/*",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
]


def generate_base_headers() -> Dict[str, str]:
    """
    Generate randomized base headers for HTTP requests.
    These headers vary on each call to avoid detection.
    
    Returns:
        Dict of HTTP headers with randomized values
    """
    # Get random User-Agent and matching Sec-Ch-Ua headers
    user_agent, sec_ch_headers = get_user_agent_with_headers()
    
    # Build base headers with randomization
    headers = {
        'User-Agent': user_agent,
        'Accept': random.choice(ACCEPT_HEADERS),
        'Accept-Language': random.choice(ACCEPT_LANGUAGES),
        'Accept-Encoding': random.choice(ACCEPT_ENCODINGS),
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }
    
    # Add Sec-Ch-Ua headers (only for Chrome/Edge, not Firefox/Safari)
    headers.update(sec_ch_headers)
    
    # Randomize header order by converting to list and shuffling
    # Note: Python 3.7+ dicts maintain insertion order
    header_items = list(headers.items())
    random.shuffle(header_items)
    randomized_headers = dict(header_items)
    
    logger.debug(f"Generated headers with User-Agent: {user_agent[:50]}...")
    
    return randomized_headers


def add_graphql_headers(
    base_headers: Dict[str, str],
    csrf_token: str,
    app_id: str,
    asbd_id: str = "359341",
    bloks_version_id: str = "41a4871badc8ef00114860033dd42edcd50935d511345a5a37fbaa878479ad3c",
    lsd_token: str = "",
    friendly_name: str = "",
    root_field_name: str = ""
) -> Dict[str, str]:
    """
    Add Instagram GraphQL-specific headers to base headers.
    
    Args:
        base_headers: Base HTTP headers from generate_base_headers()
        csrf_token: CSRF token from session
        app_id: Instagram app ID
        asbd_id: ASBD identifier
        bloks_version_id: Bloks version hash
        lsd_token: Optional LSD token
        friendly_name: GraphQL query friendly name
        root_field_name: GraphQL root field name
    
    Returns:
        Headers dict with GraphQL-specific headers added
    """
    headers = base_headers.copy()
    
    # Add GraphQL-specific headers
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    headers['X-IG-App-ID'] = app_id
    headers['X-ASBD-ID'] = asbd_id
    headers['X-Bloks-Version-Id'] = bloks_version_id
    headers['X-CSRFToken'] = csrf_token
    
    if lsd_token:
        headers['X-FB-LSD'] = lsd_token
    
    if friendly_name:
        headers['X-FB-Friendly-Name'] = friendly_name
    
    if root_field_name:
        headers['X-IG-Root-Field-Name'] = root_field_name
    
    return headers


def generate_viewport_headers() -> Dict[str, str]:
    """
    Generate realistic viewport-related headers.
    These can be used for additional fingerprint variation.
    
    Returns:
        Dict of viewport headers
    """
    # Common desktop viewport widths
    viewports = [1920, 1680, 1440, 1366, 1536, 2560]
    viewport_width = random.choice(viewports)
    
    return {
        'Viewport-Width': str(viewport_width),
        'Sec-Ch-Viewport-Width': str(viewport_width),
    }


def shuffle_header_order(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Randomize the order of headers.
    Some servers fingerprint based on header order.
    
    Args:
        headers: Dict of headers to shuffle
    
    Returns:
        New dict with same headers in random order
    """
    items = list(headers.items())
    random.shuffle(items)
    return dict(items)
