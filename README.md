# Instagram Scraper API

A lightweight FastAPI service that uses Instagram's GraphQL API to search users and fetch profiles. No database required, no login needed, all data fetched in real-time with in-memory caching.

## Features

- **Search Users**: Find users by username/name using Instagram's official GraphQL API
- **Fetch Profiles**: Get detailed profile information including bio, follower counts, and posts
- **In-Memory Cache**: 1-hour TTL cache to reduce API calls and improve response times
- **Rate Limiting Protection**: Random delays (1-3s) between requests to avoid blocks
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
CACHE_TTL=3600
REQUEST_TIMEOUT=10
MIN_DELAY=1
MAX_DELAY=3
```

### 4) Run the API server (Python)
```bash
python main.py

**Health Check**
```bash
curl http://localhost:8000/health
```How It Works

### Search Endpoint
Uses Instagram's GraphQL API (`/graphql/query`) - the same API their web interface uses:
- Sends POST requests with doc_id `24146980661639222` (search query identifier)
- Includes CSRF token for authentication
- Returns structured JSON with user data (username, full name, profile pic, verification)
- No follower counts in search results (limitation of Instagram's search API)

### Profile Endpoint
ParAPI Response Examples

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
This project is for educational/demo purposes only. Respect Instagram's Terms of Service and user privacy. The authors are not responsible for misuse.>` or `profile:<username>:<posts>`
- Significantly reduces requests to Instagram
- Improves response time for repeated queries

## Rate Limiting & Best Practices
- Random delays (1-3 seconds) between requests mimic human behavior
- Instagram may block aggressive scraping patterns
- Respect rate limits: don't make more than 10-20 requests/minute
- Use caching effectively to minimize API calls
- Consider implementing exponential backoff for production use
# Profile only
curl "http://localhost:8000/profile/cristiano"

# Profile with 12 recent posts
curl "http://localhost:8000/profile/cristiano?posts=12"
``

### 5) Try the endpoints
- Health: `GET http://localhost:8000/health`
- Search users: `GET http://localhost:8000/search?q=cristiano&limit=10`
- Fetch profile: `GET http://localhost:8000/profile/cristiano`

## Notes on scraping & rate limits
- This service uses Instagram's GraphQL API for search (more reliable than HTML scraping).
- Instagram applies strict rate limiting and anti-bot protections; expect intermittent blocks if you make too many requests.
- The service adds small random delays and uses caching to reduce request volume.
- Search results return username, full name, profile pic, and verification status (follower counts not included in search API).

## Security
- Store credentials securely (env vars, secrets manager).
- Do not hardcode credentials in code or VCS.

## Disclaimer
This project is for educational/demo purposes. Respect Instagram's ToS and user privacy. The authors are not responsible for misuse.

## macOS setup tips
- If `pip install` fails on newer Python, install Python 3.12:
	- Using Homebrew: `brew install python@3.12`
	- Create venv: `python3.12 -m venv .venv && source .venv/bin/activate`
	- Then: `pip install -r requirements.txt`
