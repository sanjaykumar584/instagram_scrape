"""
User-Agent rotation pool with realistic browser fingerprints.
Provides diverse User-Agents and matching browser metadata to avoid detection.
"""

import random
from typing import Dict, List, Tuple
from logger_config import get_logger

logger = get_logger("user_agent_pool")

# Realistic User-Agent pool covering major browsers and platforms
USER_AGENTS = [
    # Chrome on Windows
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "131",
        "platform": "Windows",
        "platform_version": "10.0",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "130",
        "platform": "Windows",
        "platform_version": "10.0",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "131",
        "platform": "Windows",
        "platform_version": "11.0",
        "mobile": False
    },
    
    # Chrome on macOS
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "131",
        "platform": "macOS",
        "platform_version": "10_15_7",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "130",
        "platform": "macOS",
        "platform_version": "10_15_7",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "131",
        "platform": "macOS",
        "platform_version": "14_1",
        "mobile": False
    },
    
    # Chrome on Linux
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "131",
        "platform": "Linux",
        "platform_version": "",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "browser": "Chrome",
        "version": "130",
        "platform": "Linux",
        "platform_version": "",
        "mobile": False
    },
    
    # Firefox on Windows
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "browser": "Firefox",
        "version": "122",
        "platform": "Windows",
        "platform_version": "10.0",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "browser": "Firefox",
        "version": "121",
        "platform": "Windows",
        "platform_version": "10.0",
        "mobile": False
    },
    
    # Firefox on macOS
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
        "browser": "Firefox",
        "version": "122",
        "platform": "macOS",
        "platform_version": "10.15",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.1; rv:122.0) Gecko/20100101 Firefox/122.0",
        "browser": "Firefox",
        "version": "122",
        "platform": "macOS",
        "platform_version": "14.1",
        "mobile": False
    },
    
    # Firefox on Linux
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "browser": "Firefox",
        "version": "122",
        "platform": "Linux",
        "platform_version": "",
        "mobile": False
    },
    
    # Safari on macOS
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "browser": "Safari",
        "version": "17.2",
        "platform": "macOS",
        "platform_version": "10_15_7",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "browser": "Safari",
        "version": "17.2",
        "platform": "macOS",
        "platform_version": "14_1",
        "mobile": False
    },
    
    # Edge on Windows
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "browser": "Edge",
        "version": "131",
        "platform": "Windows",
        "platform_version": "10.0",
        "mobile": False
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        "browser": "Edge",
        "version": "130",
        "platform": "Windows",
        "platform_version": "10.0",
        "mobile": False
    },
]


def get_random_user_agent() -> Dict[str, any]:
    """
    Select a random User-Agent with matching metadata.
    
    Returns:
        Dict containing:
        - ua: User-Agent string
        - browser: Browser name
        - version: Browser version
        - platform: Platform name
        - platform_version: Platform version
        - mobile: Is mobile device
    """
    ua_data = random.choice(USER_AGENTS)
    logger.debug(f"Selected User-Agent: {ua_data['browser']} {ua_data['version']} on {ua_data['platform']}")
    return ua_data.copy()


def generate_sec_ch_ua_headers(ua_data: Dict[str, any]) -> Dict[str, str]:
    """
    Generate Sec-Ch-Ua headers that match the User-Agent.
    These headers provide browser metadata to the server.
    
    Args:
        ua_data: User-Agent data dict from get_random_user_agent()
    
    Returns:
        Dict with Sec-Ch-Ua-* headers
    """
    headers = {}
    
    if ua_data['browser'] == 'Chrome':
        # Chrome Sec-Ch-Ua format
        version = ua_data['version']
        headers['Sec-Ch-Ua'] = f'"Google Chrome";v="{version}", "Chromium";v="{version}", "Not_A Brand";v="24"'
        headers['Sec-Ch-Ua-Mobile'] = '?0'
        headers['Sec-Ch-Ua-Platform'] = f'"{ua_data["platform"]}"'
        
    elif ua_data['browser'] == 'Edge':
        # Edge Sec-Ch-Ua format
        version = ua_data['version']
        headers['Sec-Ch-Ua'] = f'"Microsoft Edge";v="{version}", "Chromium";v="{version}", "Not_A Brand";v="24"'
        headers['Sec-Ch-Ua-Mobile'] = '?0'
        headers['Sec-Ch-Ua-Platform'] = f'"{ua_data["platform"]}"'
        
    elif ua_data['browser'] == 'Firefox':
        # Firefox doesn't send Sec-Ch-Ua headers (as of 2024)
        # Omit these headers entirely for Firefox
        pass
        
    elif ua_data['browser'] == 'Safari':
        # Safari doesn't send Sec-Ch-Ua headers
        # Omit these headers entirely for Safari
        pass
    
    return headers


def get_user_agent_with_headers() -> Tuple[str, Dict[str, str]]:
    """
    Get a random User-Agent string with matching Sec-Ch-Ua headers.
    Convenience function for getting both at once.
    
    Returns:
        Tuple of (user_agent_string, sec_ch_headers_dict)
    """
    ua_data = get_random_user_agent()
    user_agent = ua_data['ua']
    sec_ch_headers = generate_sec_ch_ua_headers(ua_data)
    
    return user_agent, sec_ch_headers
