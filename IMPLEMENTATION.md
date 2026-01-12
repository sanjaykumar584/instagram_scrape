# Instagram Scraper - Technical Implementation Details

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [GraphQL API Integration](#graphql-api-integration)
3. [Request Flow](#request-flow)
4. [Authentication & CSRF Tokens](#authentication--csrf-tokens)
5. [Caching Strategy](#caching-strategy)
6. [HTML Parsing for Profiles](#html-parsing-for-profiles)
7. [Error Handling & Rate Limiting](#error-handling--rate-limiting)
8. [Code Structure](#code-structure)
9. [Production Hardening Plan](#production-hardening-plan)

---

## Architecture Overview

The scraper uses a three-layer architecture:

```
FastAPI Server (main.py)
    ↓
Scraper Service (scraper.py)
    ↓
HTTP Session + Instagram APIs
```

### Components

1. **main.py** - FastAPI application

   - Defines REST endpoints (`/search`, `/profile`, `/health`)
   - Handles caching logic
   - Formats responses

2. **scraper.py** - Core scraper logic

   - Manages HTTP sessions
   - Implements GraphQL queries
   - Parses HTML responses

3. **cache.py** - In-memory cache
   - TTL-based expiration
   - Key-value storage

---

## GraphQL API Integration

### What is GraphQL?

GraphQL is a query language for APIs. Instagram uses it internally for data fetching. Instead of sending human-readable form data, we send structured queries via GraphQL.

### The Search Endpoint

**Endpoint:** `https://www.instagram.com/graphql/query`

**Method:** POST

**Content-Type:** `application/x-www-form-urlencoded`

### Key Identifiers

```python
# In scraper.py __init__:
self.search_doc_id = '24146980661639222'  # GraphQL document ID for search
self.app_id = '936619743392459'           # Instagram's web app ID
```

These IDs tell Instagram:

- Which query to execute (doc_id)
- Which application is making the request (app_id)

### Building the Request

```python
def search_users(self, query: str, limit: int = 20) -> List[Dict]:
    # 1. Prepare headers
    headers = self.headers.copy()
    headers['X-IG-App-ID'] = self.app_id
    headers['X-CSRFToken'] = self.csrf_token

    # 2. Build GraphQL variables
    variables = {
        "data": {
            "context": "blended",              # Search across all types
            "include_reel": "true",            # Include Stories/Reels
            "query": query,                    # User's search term
            "rank_token": "",                  # Ranking token (optional)
            "search_session_id": str(int(time.time() * 1000)),  # Unique session
            "search_surface": "web_top_search" # Where search originated
        },
        "hasQuery": True
    }

    # 3. Prepare form data
    data = {
        'variables': json.dumps(variables),
        'doc_id': self.search_doc_id
    }

    # 4. Send request
    response = self.session.post(
        self.graphql_url,
        headers=headers,
        data=data,
        timeout=REQUEST_TIMEOUT
    )
```

### Response Structure

Instagram returns a nested JSON response:

```json
{
  "data": {
    "xdt_api__v1__fbsearch__topsearch_connection": {
      "users": [
        {
          "position": 0,
          "user": {
            "username": "cristiano",
            "full_name": "Cristiano Ronaldo",
            "is_verified": true,
            "profile_pic_url": "https://...",
            "pk": "123456789",
            "id": "123456789"
          }
        }
        // ... more users
      ],
      "rank_token": "1768215190291|..."
    }
  },
  "extensions": {
    "is_final": true,
    "server_metadata": {
      "request_start_time_ms": 1768215190221,
      "time_at_flush_ms": 1768215191166
    }
  },
  "status": "ok"
}
```

### Parsing the Response

```python
# Extract the search results
search_data = result.get('data', {}).get('xdt_api__v1__fbsearch__topsearch_connection', {})
user_items = search_data.get('users', [])[:limit]

# Transform into our format
users = []
for item in user_items:
    user = item.get('user', {})
    users.append({
        'username': user.get('username'),
        'full_name': user.get('full_name'),
        'profile_pic': user.get('profile_pic_url'),
        'is_verified': user.get('is_verified', False),
        'follower_count': 0,  # Not in search results
        'is_private': False   # Not in search results
    })
```

---

## Request Flow

### Complete Flow for `/search?q=cristiano&limit=5`

```
1. User sends: GET /search?q=cristiano&limit=5
   ↓
2. FastAPI main.py receives request
   ├─ Generate cache key: "search:cristiano:5"
   ├─ Check cache.get("search:cristiano:5")
   └─ If cached: return cached result

3. Cache miss, so call scraper.search_users("cristiano", 5)
   ├─ Scraper adds random delay (1-3 seconds)
   ├─ Build headers with CSRF token
   ├─ Build GraphQL variables
   ├─ POST to Instagram's GraphQL endpoint
   ├─ Parse JSON response
   ├─ Extract user data
   └─ Return list of dicts

4. FastAPI formats response:
   {
     "success": true,
     "results": [...],
     "count": 5
   }

5. Cache the result: cache.set("search:cristiano:5", response)
   ↓
6. Return response to user
   ↓
7. Next request for same query uses cache (no API call for 1 hour)
```

### Complete Flow for `/profile/cristiano`

```
1. User sends: GET /profile/cristiano?posts=12
   ↓
2. FastAPI receives request
   ├─ Generate cache key: "profile:cristiano:12"
   ├─ Check cache
   └─ If cached: return cached result

3. Cache miss, so call scraper.get_profile("cristiano", include_posts=True, post_limit=12)
   ├─ Add random delay
   ├─ GET https://instagram.com/cristiano/
   ├─ Parse HTML response
   │  ├─ Look for <script type="application/json"> tags
   │  ├─ Recursively search for user data in JSON
   │  ├─ Extract:
   │  │  ├─ username, full_name, biography
   │  │  ├─ follower_count, following_count, post_count
   │  │  ├─ is_verified, is_private
   │  │  ├─ profile_pic_url, external_url
   │  │  └─ posts (if requested)
   │  └─ Return dict with profile and posts

4. FastAPI formats response:
   {
     "success": true,
     "profile": {...},
     "posts": [...]
   }

5. Cache the result
   ↓
6. Return to user
```

---

## Authentication & CSRF Tokens

### What is CSRF Token?

CSRF (Cross-Site Request Forgery) token is a security measure that prevents unauthorized requests:

- Instagram only accepts POST requests with valid CSRF token
- Token is extracted from Instagram's initial response
- Token is session-specific

### Token Extraction

```python
def _init_session(self):
    """Initialize session and get CSRF token"""
    try:
        # 1. Send initial request to Instagram homepage
        response = self.session.get(
            self.base_url,
            headers=self.headers,
            timeout=REQUEST_TIMEOUT
        )

        # 2. Extract from response cookies
        self.csrf_token = response.cookies.get('csrftoken', '')

        # 3. If not in cookies, look for it in HTML
        if not self.csrf_token:
            m = re.search(r'"csrf_token":"([^"]+)"', response.text)
            if m:
                self.csrf_token = m.group(1)
    except Exception:
        self.csrf_token = ''
```

### Token in Requests

```python
# Every POST request includes the CSRF token:
headers['X-CSRFToken'] = self.csrf_token

# The session also maintains cookies automatically
self.session.cookies.set_cookie(cookie)
```

---

## Caching Strategy

### Cache Implementation (cache.py)

```python
class SimpleCache:
    def __init__(self, ttl: int = None):
        # TTL from env or default 3600 seconds (1 hour)
        default_ttl = int(os.getenv("CACHE_TTL", "3600") or 3600)
        self.cache = {}  # Internal dict: key -> (value, expiry_time)
        self.ttl = ttl if ttl is not None else default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value if not expired"""
        item = self.cache.get(key)
        if not item:
            return None
        value, expiry = item
        if time.time() < expiry:
            return value
        # Expired, clean up and return None
        self.cache.pop(key, None)
        return None

    def set(self, key: str, value: Any):
        """Store value with expiry time"""
        expiry = time.time() + self.ttl
        self.cache[key] = (value, expiry)
```

### Cache Keys

```python
# Search requests
cache_key = f"search:{query}:{limit}"
# Example: "search:cristiano:10"

# Profile requests
cache_key = f"profile:{username}:{posts}"
# Example: "profile:cristiano:12"
```

### Cache Flow

```
Request comes in
    ↓
Generate cache_key = f"search:{q}:{limit}"
    ↓
cached = cache.get(cache_key)
    ├─ If found and not expired: return cached
    └─ If not found or expired: continue
    ↓
Make API request to Instagram
    ↓
Receive response
    ↓
Format response dict
    ↓
cache.set(cache_key, response_dict)
    ↓
Return response
    ↓
(Next identical request within 1 hour uses cache - NO API CALL!)
```

### Benefits

- Reduces API calls to Instagram (avoids rate limiting)
- Faster response times (memory lookup vs HTTP request)
- Enables offline-like behavior for recent queries

---

## HTML Parsing for Profiles

### Why HTML Parsing?

Instagram's GraphQL API doesn't provide:

- Follower/following counts in search results
- Post data
- Full profile details for non-authenticated users

So we parse the public HTML profile page instead.

### Profile Page Data Locations

Instagram embeds JSON data in the HTML page in several ways:

**Method 1: JSON Script Tags**

```html
<script type="application/json">
  {
    "require": [[...], [...], ...]
  }
</script>
```

These contain the full profile data in a nested structure.

**Method 2: JSON-LD Structured Data** (fallback)

```html
<script type="application/ld+json">
  {
    "@type": "Person",
    "name": "Cristiano Ronaldo",
    "image": "https://..."
  }
</script>
```

### Extraction Process

```python
def get_profile(self, username: str, include_posts: bool = False, post_limit: int = 12):
    # 1. Fetch the profile page
    response = self.session.get(f"{self.base_url}/{username}/", ...)

    # 2. Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')

    # 3. Find all JSON script tags
    json_scripts = soup.find_all('script', type='application/json')

    # 4. Search for user data in nested JSON
    user_data = {}
    for script in json_scripts:
        data = json.loads(script.string)
        # Recursively search for user fields
        user_data = self._extract_user_from_nested(data)
        if user_data:
            break

    # 5. Extract specific fields
    profile = {
        'username': user_data.get('username'),
        'full_name': user_data.get('full_name'),
        'biography': user_data.get('biography'),
        'follower_count': user_data.get('edge_followed_by', {}).get('count', 0),
        'following_count': user_data.get('edge_follow', {}).get('count', 0),
        'post_count': user_data.get('edge_owner_to_timeline_media', {}).get('count', 0),
        # ... more fields
    }
```

### Recursive Search

```python
def _extract_user_from_nested(self, data: Dict) -> Optional[Dict]:
    """Recursively search nested dict for user data"""
    if not isinstance(data, dict):
        return None

    # Check if this dict has user fields
    if 'username' in data and 'full_name' in data:
        return data

    # Check if data contains a 'user' key
    if 'user' in data and isinstance(data['user'], dict):
        return data['user']

    # Recursively search values
    for value in data.values():
        if isinstance(value, dict):
            result = self._extract_user_from_nested(value)
            if result:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = self._extract_user_from_nested(item)
                    if result:
                        return result

    return None
```

### Posts Extraction

```python
def _extract_posts(self, user_data: Dict, limit: int) -> List[Dict]:
    """Extract recent posts from user data"""
    posts = []
    try:
        # Navigate to posts array
        edges = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])

        for edge in edges[:limit]:
            node = edge.get('node', {})
            posts.append({
                'shortcode': node.get('shortcode'),      # Post ID
                'caption': node.get('text', ''),          # Post caption
                'like_count': node.get('edge_liked_by', {}).get('count', 0),
                'comment_count': node.get('edge_media_to_comment', {}).get('count', 0),
                'timestamp': node.get('taken_at_timestamp'),
                'media_url': node.get('display_url'),
                'is_video': node.get('is_video', False)
            })
    except Exception:
        pass

    return posts
```

---

## Error Handling & Rate Limiting

### Rate Limiting Strategy

```python
def _random_delay(self):
    """Add random delay to mimic human behavior"""
    # Delay between MIN_DELAY and MAX_DELAY (default 1-3 seconds)
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
```

Called before every API request to:

- Avoid hitting rate limits
- Mimic human browsing patterns
- Make requests appear organic to Instagram

### Error Handling

**Search Errors:**

```python
try:
    response = self.session.post(url, ...)

    if response.status_code == 200:
        # Process response
        return users

    return []  # Any non-200 returns empty

except Exception:
    # Network error, JSON parse error, etc.
    return []
```

**Profile Errors:**

```python
try:
    response = self.session.get(url, ...)

    if response.status_code == 404:
        return None  # User doesn't exist

    if response.status_code != 200:
        return None  # Other errors

    # Parse and extract
    return {'profile': profile, 'posts': posts}

except Exception:
    return None
```

### FastAPI Error Responses

```python
@app.get("/profile/{username}")
async def get_profile(username: str, posts: int = Query(0, ge=0, le=50)):
    try:
        profile_data = scraper.get_profile(username, ...)

        if not profile_data:
            # 404 if profile not found
            raise HTTPException(
                status_code=404,
                detail=f"Profile '{username}' not found"
            )

        return {"success": True, ...}

    except HTTPException:
        raise  # Re-raise HTTP errors

    except Exception as e:
        # 500 for unexpected errors
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Code Structure

### File Organization

```
instgram-scrape/
├── main.py              # FastAPI server + endpoints
├── scraper.py           # Core scraping logic
├── cache.py             # In-memory cache
├── requirements.txt     # Dependencies
├── .env.example         # Environment variables template
├── .env                 # Actual env variables (git-ignored)
├── README.md            # User guide
├── IMPLEMENTATION.md    # This file
└── app/                 # Old folder (deprecated)
    └── data/            # Cache data storage
```

### Key Classes

**InstagramScraper**

- `__init__()`: Initialize session, get CSRF token
- `_init_session()`: Setup HTTP session
- `_random_delay()`: Rate limiting delay
- `search_users()`: GraphQL search
- `get_profile()`: HTML profile parsing
- `_extract_posts()`: Extract posts from profile data
- `_extract_shared_data()`: Regex-based data extraction
- `_extract_user_from_nested()`: Recursive JSON search

**SimpleCache**

- `get(key)`: Retrieve cached value
- `set(key, value)`: Store value with TTL
- `clear()`: Empty cache

### Main.py Endpoints

```python
@app.on_event("startup")
def startup_event():
    # Initialize scraper when server starts
    pass

@app.get("/health")
async def health_check():
    # Return server status

@app.get("/search")
async def search_users(q: str, limit: int = 20):
    # Search with cache

@app.get("/profile/{username}")
async def get_profile(username: str, posts: int = 0):
    # Get profile with cache
```

---

## Key Dependencies

| Package          | Purpose               |
| ---------------- | --------------------- |
| `fastapi`        | REST API framework    |
| `uvicorn`        | ASGI server           |
| `requests`       | HTTP client           |
| `beautifulsoup4` | HTML parsing          |
| `python-dotenv`  | Environment variables |

---

## Environment Variables

```bash
# .env file
CACHE_TTL=3600          # Cache expiration (seconds)
REQUEST_TIMEOUT=10      # HTTP request timeout (seconds)
MIN_DELAY=1             # Minimum delay between requests
MAX_DELAY=3             # Maximum delay between requests
```

---

## Performance Characteristics

| Operation            | Time  | Notes                    |
| -------------------- | ----- | ------------------------ |
| Search (first call)  | 2-5s  | GraphQL API + 1-3s delay |
| Search (cached)      | <10ms | Memory lookup            |
| Profile (first call) | 3-8s  | HTML parse + 1-3s delay  |
| Profile (cached)     | <10ms | Memory lookup            |
| Cache expiry         | 3600s | Configurable via env     |

---

## Security Considerations

1. **CSRF Protection**: Tokens are extracted and validated by Instagram
2. **Rate Limiting**: Random delays prevent aggressive scraping
3. **No Data Storage**: All data held in memory, not persisted
4. **No Authentication**: Works with public data only
5. **SSL/TLS**: All requests use HTTPS

### Limitations

- Instagram actively blocks scrapers
- May get temporarily blocked if too many requests
- GraphQL doc_id and app_id may change in future Instagram updates
- HTML structure changes break profile parsing

---

## Debugging Tips

**Enable Verbose Logging:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Test Individual Components:**

```python
from scraper import InstagramScraper

s = InstagramScraper()
print("CSRF Token:", s.csrf_token)

results = s.search_users("cristiano", 5)
print("Search results:", results)

profile = s.get_profile("cristiano", include_posts=True, post_limit=3)
print("Profile:", profile)
```

**Check Cache:**

```python
from cache import SimpleCache

cache = SimpleCache(ttl=3600)
cache.set("test_key", {"data": "value"})
print(cache.get("test_key"))
```

---

## Future Improvements

1. **Redis Caching**: Replace in-memory cache with Redis for distributed caching
2. **GraphQL Profile**: Use GraphQL for profile fetching instead of HTML parsing
3. **Rate Limit Headers**: Track X-RateLimit headers from Instagram
4. **Retry Logic**: Implement exponential backoff for failed requests
5. **Database**: Store scraping history and user metadata
6. **Authentication**: Support Instagram login for more data access
7. **Proxy Support**: Route requests through proxies to avoid blocks
8. **Webhook**: Push notifications when profiles are updated

---

## Production Hardening Plan

### Key Risks Right Now

- Silent failures: exceptions are swallowed in the scraper and return empty data with no visibility.
- Rate limiting and blocks: fixed 1-3s delays with no detection of 429/403/401 or Retry-After guidance.
- Session fragility: CSRF token and cookies are fetched once and never refreshed; expiry leads to steady failures.
- Concurrency hazards: shared cache and session are not thread-safe; races under load can corrupt state.
- Fragile parsing: hardcoded GraphQL doc_id/app_id and brittle HTML JSON extraction; minor Instagram changes break it.
- No observability: no structured logs, metrics, or health checks beyond uptime.
- Network resilience: no retries or backoff; timeouts surface as empty results.
- Unbounded cache: in-memory dict has no limits or eviction; memory growth with unique queries.

### What Will Break in Production

- CSRF token expiration → every POST returns 401/403 and search becomes empty.
- Instagram rate-limits or blocks the IP → scraper returns empty arrays; callers cannot tell block vs no results.
- HTML layout change → profile parsing fails; API returns 404 “not found” even when the user exists.
- Burst traffic → cache/session races, blocking I/O stalls the event loop, memory bloat from cache.
- Network jitter/timeouts → requests fail with no retry; perceived as “no results”.

### Hardening Steps (Suggested Order)

1. **Logging and diagnostics**

- Add structured logging (timestamp, request_id, path, status, elapsed_ms, error_kind) at entry/exit of search/profile.
- Log non-200 responses from Instagram with status code and body snippet; log cache hits/misses and retries.

2. **Error handling and response hygiene**

- Differentiate client errors (400-range) vs server/transient (500/timeout) and map to meaningful API responses.
- Return “upstream_unavailable” vs “not_found” vs “rate_limited”; avoid silent empty lists on errors.

3. **Rate-limit detection and backoff**

- Detect 429/403/401 and parse Retry-After; implement exponential backoff with jitter; add a circuit breaker to pause.
- Serialize outbound requests with a token bucket or leaky bucket to keep RPS low and steady.

4. **Session and CSRF management**

- Refresh CSRF token and cookies when 401/403/400 occurs; add proactive refresh on a timer; isolate session per worker.
- Persist cookie jar across restarts; clear and re-init on consecutive auth failures.

5. **Thread-safe, bounded caching**

- Replace dict cache with Redis or, at minimum, a thread-safe LRU with max size and TTL; guard mutations with a lock.
- Cache negative lookups separately with short TTL to avoid hammering nonexistent users.

6. **Network resilience**

- Add retries with exponential backoff for connection/read timeouts and 5xx; separate connect_timeout vs read_timeout.
- Configure HTTP connection pooling limits; surface retry counts in logs and metrics.

7. **Parsing robustness and configurability**

- Make doc_id/app_id configurable via environment; add fallback IDs and a health probe to verify they still work.
- Validate response schema before parsing; if parsing fails, return a 502 with an explicit “parse_error” code and log a sample payload.

8. **Observability and health**

- Expose metrics: request counts, error counts by type, cache hit rate, Instagram status codes, latency percentiles, retry counts.
- Add health checks that verify: can reach instagram.com, CSRF token is valid, search GraphQL responds with expected shape.

9. **Scalability and isolation**

- Make scraper I/O async or move to worker threads; ensure FastAPI handlers do not block the event loop.
- Isolate per-request state; avoid global shared session unless protected; consider a small session pool.

10. **Security and abuse controls**

- Add API authentication (key or JWT) to your endpoints; rate-limit per caller; log caller identity in every request.

### Minimal Viable Production Checklist

- Structured logging + error codes in responses.
- Retry with exponential backoff and block detection (429/403/401) plus a circuit breaker.
- CSRF/cookie refresh on failure plus periodic refresh.
- Redis (or thread-safe bounded cache) with TTL and max size.
- Health check that exercises Instagram (lightweight ping plus schema check).
- Metrics for requests, errors by type, latency, retries, cache hit rate, and Instagram status codes.
- Configurable doc_id/app_id via environment with startup validation.
- Input validation for q, username, and posts; sanitize and length-limit.

### Stretch Improvements (Post-MVP)

- Proxy rotation or IP pool to reduce block probability.
- Separate search and profile workers with a queue to control outbound rate.
- Persistent session store and scheduled token refresh job.
- Feature flag for switching to GraphQL-based profile fetch when a stable doc_id is found.
