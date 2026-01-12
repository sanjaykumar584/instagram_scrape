# Instagram Scraper API

A lightweight FastAPI service that uses Instagram's GraphQL API to search users and fetch profiles. No database required, no login needed, all data fetched in real-time.

## Features

- **Search Users**: Find users by username/name using Instagram's official GraphQL API
- **Fetch Profiles**: Get detailed profile information including bio, follower counts, and posts
- **Smart Rate Limiting**: Random delays (1-3s) between requests to avoid blocks
- **Anti-Detection**: User-Agent rotation, header randomization, session refresh to avoid Instagram blocks
- **Reliable**: Automatic session refresh every 50 requests or 30 minutes with fresh fingerprints
- **No Authentication**: Works without Instagram login (public data only)

> **Note**: Accessing Instagram programmatically may violate their Terms of Service. Use responsibly for educational purposes only, with proper consent, and comply with all applicable laws and platform policies.

## Quick Start

### 1) Prerequisites

- Python 3.12 (recommended)
- No Instagram login required (public scraping only)

### 2) Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Configure environment (optional)

Copy `.env.example` to `.env` and adjust settings:

```
REQUEST_TIMEOUT=10
MIN_DELAY=1
MAX_DELAY=3
SESSION_REFRESH_REQUESTS=50      # Refresh after N requests (default: 50)
SESSION_REFRESH_SECONDS=1800     # Refresh after N seconds (default: 30 min)
```

### 4) Run the API server (Python)

```bash
python main.py
```

### 5) Try the endpoints (cURL)

```bash
# Health
curl -s http://localhost:8000/health | jq .

# Search users
curl -s "http://localhost:8000/search?q=cristiano&limit=5" | jq .

# Profile only
curl -s "http://localhost:8000/profile/cristiano" | jq .

# Profile with 12 recent posts
curl -s "http://localhost:8000/profile/cristiano?posts=12" | jq .
```

## How It Works

### Search Endpoint

Uses Instagram's GraphQL API (`/graphql/query`) - the same API their web interface uses:

- Sends POST requests with doc_id `24146980661639222` (search query identifier)
- Includes CSRF token for authentication
- Returns structured JSON with user data (username, full name, profile pic, verification)
- No follower counts in search results (limitation of Instagram's search API)

### Profile Endpoint

API Response Examples

**Search Response**

```json
{
  "success": true,
  "results": [
    {
      "username": "cristiano",
      "full_name": "Cristiano Ronaldo",
      "profile_pic": "https://...",
      "is_verified": true,
      "follower_count": 0,
      "is_private": false
    }
  ],
  "count": 1
}
```

**Profile Response**

```json
{
  "success": true,
  "profile": {
    "username": "cristiano",
    "full_name": "Cristiano Ronaldo",
    "biography": "...",
    "follower_count": 500000000,
    "following_count": 500,
    "post_count": 3500,
    "is_verified": true,
    "is_private": false,
    "profile_pic_url": "https://...",
    "external_url": "..."
  },
  "posts": []
}
```

## Anti-Detection Features

To avoid Instagram blocking the scraper, several anti-detection measures are implemented:

### 1. User-Agent Rotation
- Each session uses a different User-Agent from a pool of 16 realistic browsers
- Includes Chrome, Firefox, Safari, and Edge on Windows, macOS, and Linux
- Sec-Ch-Ua headers automatically match the selected User-Agent

### 2. Header Randomization
- Accept-Language varies across 8 different locale options
- Accept-Encoding order is randomized
- Header order is shuffled to avoid fingerprinting
- All vary per request for maximum variance

### 3. Session Refresh
- Sessions automatically refresh after 50 requests OR 30 minutes
- Each refresh generates a fresh User-Agent and headers
- CSRF tokens are refreshed automatically
- Prevents detection based on session age

### 4. Request Timing
- Random delays (1-3 seconds) between requests
- Mimics human browsing behavior
- Configurable via MIN_DELAY and MAX_DELAY

## Troubleshooting

**Empty search results**

- Instagram may be blocking requests; wait a few minutes and retry
- Try exact usernames instead of partial searches
- Check CSRF token is being retrieved (check logs)

**Profile fetch fails**

- Profile may be private or doesn't exist
- Instagram changed their HTML structure (scraper may need updates)
- Rate limited - wait before retrying

**macOS Python 3.14 build errors**

- Use Python 3.12: `brew install python@3.12`
- Create venv: `python3.12 -m venv .venv && source .venv/bin/activate`
- Then: `pip install -r requirements.txt`

## Disclaimer

This project is for educational/demo purposes only. Respect Instagram's Terms of Service and user privacy. The authors are not responsible for misuse.

## Rate Limiting & Best Practices

- Random delays (1-3 seconds) between requests mimic human behavior
- Instagram may block aggressive scraping patterns
- Respect rate limits: don't make more than 50-100 requests/minute
- The scraper automatically rotates sessions every 50 requests
- Consider spreading requests over time for long-term reliability
- Monitor logs for rate limit warnings (HTTP 429)

## Security

- Store credentials securely (env vars, secrets manager).
- Do not hardcode credentials in code or VCS.

## macOS setup tips

- If `pip install` fails on newer Python, install Python 3.12:
  - Using Homebrew: `brew install python@3.12`
  - Create venv: `python3.12 -m venv .venv && source .venv/bin/activate`
  - Then: `pip install -r requirements.txt`
