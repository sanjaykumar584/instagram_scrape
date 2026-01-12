# Detailed Technical Guide: From Cookies to Results

## Part 1: Understanding Cookies and Sessions

### What are Cookies?

Cookies are **small text files** that Instagram gives your browser to remember you. Think of them as **loyalty cards** at a store.

#### Real World Example:

```
1. You go to Starbucks for the first time
   Starbucks: "Welcome! Here's your loyalty card with ID: xyz123"
   (They give you a card)

2. You go to Starbucks again
   You: *show loyalty card*
   Starbucks: "Oh, it's you! I remember you, here's your coffee"
   (They recognize you from the card)
```

**Instagram does the same with cookies:**

```
1. First visit to instagram.com
   Instagram: "Here's your session cookie"
   Browser saves: session_id=abc123, session_hash=def456

2. Next visit to instagram.com
   Browser sends: "Here's my session_id=abc123"
   Instagram: "I remember you! Here's your data"
```

### How Cookies Work in HTTP

#### Step 1: Browser Gets Cookie from Server

**Your API makes request:**

```http
GET / HTTP/1.1
Host: instagram.com
User-Agent: Mozilla/5.0...
```

**Instagram's response:**

```http
HTTP/1.1 200 OK
Set-Cookie: sessionid=abc123def456; Path=/; Domain=.instagram.com; HttpOnly; Secure
Set-Cookie: csrftoken=xyz789; Path=/; Domain=.instagram.com;
Content-Type: text/html
...
```

**Meaning:**

- `sessionid=abc123def456` → Unique session ID (remember me)
- `Path=/` → Valid for all paths on instagram.com
- `Domain=.instagram.com` → Valid for all subdomains
- `HttpOnly` → JavaScript can't access it (security)
- `Secure` → Only sent over HTTPS (security)

#### Step 2: Browser Stores Cookie

**In memory (while session is open):**

```
Cookies jar for instagram.com:
├── sessionid: abc123def456
├── csrftoken: xyz789
├── ds_user_id: 9876543
├── mid: ABCD1234
└── (other cookies)
```

#### Step 3: Browser Sends Cookie on Every Request

**Every future request includes:**

```http
GET /graphql/ HTTP/1.1
Host: instagram.com
User-Agent: Mozilla/5.0...
Cookie: sessionid=abc123def456; csrftoken=xyz789; ds_user_id=9876543; mid=ABCD1234
```

**Instagram verifies:**

- Is this session valid?
- Is the sessionid real?
- Has it expired?
- Is it from a real browser?

---

## Part 2: CSRF Token Fetching (Initial Setup)

### What is CSRF Token?

**CSRF = Cross-Site Request Forgery Protection**

A CSRF token is a **secret code** that proves:

1. You're using a real browser
2. You're not a bot
3. Your request is genuine

#### Why is it needed?

```
Bad guy's website says:
"Click here to win free money!"
<button onclick="steal.com/steal?action=delete_account&user=you">
```

If you click while logged into Instagram:

```
Your browser automatically sends your cookies
Instagram thinks: "This is you, delete your account"
Your account gets deleted!
```

**CSRF token prevents this:**

```
Bad guy's website can't get Instagram's CSRF token
So when they try to send request:
GET /api/delete_account?csrf=GUESSED_VALUE
Instagram checks: "Does csrf token match the one I gave you?"
NO MATCH → Rejected, your account is safe
```

### How Our API Gets CSRF Token

#### Step 1: API Starts Up

```python
# scraper.py - __init__() method
class InstagramScraper:
    def __init__(self):
        self.session = requests.Session()  # Create a new session
        self.csrf_token = None              # Initialize as None
        self.lsd = None                     # Facebook LSD token
        self._init_session()                # Fetch tokens
```

#### Step 2: Make Initial Request to Instagram Homepage

```python
# scraper.py - _init_session() method
def _init_session(self):
    """
    Fetch CSRF token and other required tokens from Instagram
    """
    logger.info("Initializing session, fetching CSRF token...")

    try:
        # NETWORK CALL #1: Download Instagram homepage
        response = self.session.get(
            'https://www.instagram.com/',
            timeout=(5, 10)  # 5s connect, 10s read
        )

        logger.debug(f"Got response status: {response.status_code}")
```

#### Step 3: What Happens at Network Level

**Our API sends:**

```http
GET / HTTP/1.1
Host: www.instagram.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-US,en;q=0.5
Connection: keep-alive
```

**Instagram's server responds:**

```http
HTTP/1.1 200 OK
Date: Mon, 12 Jan 2026 19:10:00 GMT
Server: Apache
Set-Cookie: sessionid=rnd12345678901234567890ab; Path=/; Domain=.instagram.com; HttpOnly; Secure; SameSite=Lax
Set-Cookie: csrftoken=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890; Path=/; Domain=.instagram.com; Secure; SameSite=Lax
Set-Cookie: mid=ZaBcDeF1234567890abcdef; Path=/; Domain=.instagram.com; Expires=Wed, 12 Jan 2027 19:10:00 GMT
Content-Type: text/html; charset=utf-8
Content-Length: 245892
...
<html>
  <head>
    ...
  </head>
  <body>
    ...
  </body>
</html>
```

**What happened:**

1. Instagram sent 3 cookies in `Set-Cookie` headers
2. Our requests.Session **automatically stored** these cookies
3. Now every future request will include these cookies

#### Step 4: Extract CSRF Token from HTML

```python
def _init_session(self):
    response = self.session.get('https://www.instagram.com/', timeout=(5, 10))

    # STEP 1: Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    logger.debug("Parsed HTML response")

    # STEP 2: Find the script tag containing config
    script_tag = soup.find('script', {'type': 'application/json', 'id': 'config'})

    if script_tag:
        # STEP 3: Extract JSON data
        config_data = json.loads(script_tag.string)

        # STEP 4: Get CSRF token from config
        self.csrf_token = config_data.get('csrf_token')
        logger.info(f"Extracted CSRF token: {self.csrf_token[:10]}...")

        # STEP 5: Also get LSD token (for some API calls)
        self.lsd = config_data.get('lsd')

    if not self.csrf_token:
        logger.error("Could not extract CSRF token from HTML")
        raise Exception("Failed to initialize session")
```

#### Example: What the HTML Looks Like

```html
<!DOCTYPE html>
<html>
  <head>
    ...
  </head>
  <body>
    <div id="root"></div>

    <!-- Hidden script tag with configuration -->
    <script type="application/json" id="config">
      {
        "csrf_token": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890",
        "lsd": "AVq1234567890",
        "appId": "936619743392459",
        "version": "123456",
        "userId": "9876543",
        ...
      }
    </script>

    <script src="/static/js/main.js"></script>
  </body>
</html>
```

**Our parsing extracts:** `csrf_token = "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"`

---

## Part 3: Session Management

### What is a Session?

A session is a **conversation between browser and server**.

```
Timeline:
T=0  Browser connects to Instagram
     Instagram: "Welcome! Here's your session ID"
     (gives sessionid cookie)

T=1  Browser: "Hey, here's my sessionid, give me data"
     Instagram: checks cookie, sends data

T=2  Browser: "Hey, here's my sessionid, search for 'musk'"
     Instagram: checks cookie, does search

T=100 (Session expires after 1 week)
      Browser: "Hey, here's my sessionid"
      Instagram: "This session is expired, please login again"
```

### Our Session Object

```python
# scraper.py
class InstagramScraper:
    def __init__(self):
        # Create a persistent session
        self.session = requests.Session()

        # Configure session with connection pooling
        adapter = HTTPAdapter(poolsize=10, maxsize=10)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        # This session will:
        # 1. Store cookies automatically
        # 2. Reuse connections (faster)
        # 3. Keep CSRF token valid across requests
```

### Session Life Cycle

```
1. INITIALIZATION
   ├── Create session object
   ├── Make request to instagram.com
   ├── Store cookies automatically (sessionid, csrftoken, etc)
   └── Extract CSRF token from HTML

2. ACTIVE (using the session)
   ├── Every request includes stored cookies
   ├── Every request includes X-CSRFToken header
   ├── Instagram validates both
   └── If valid: respond with data

3. TOKEN REFRESH (if token expires)
   ├── Instagram returns 401 Unauthorized
   ├── API calls _init_session() again
   ├── New CSRF token fetched
   └── Next request uses new token

4. DISCONNECTION
   └── Session is garbage collected (cookies discarded)
```

---

## Part 4: Detailed Search Request Flow

### Complete Request: Search for "musk"

#### Client Request

```
GET /search?q=musk&limit=5
```

### Step 1: FastAPI Receives Request

```python
# main.py
@app.get("/search")
async def search_users(q: str, limit: int = 10):
    # STEP 1: Generate request ID
    request_id = str(uuid.uuid4())[:8]  # Example: "78bf3c7d"
    logger.info(f"[{request_id}] SEARCH q={q}, limit={limit}")

    # Log: "19:09:13 - api - INFO - [search_users:45] - [78bf3c7d] SEARCH q=musk, limit=5"
```

### Step 2: Check Rate Limiter

```python
    # STEP 2: Check if we're blocked by rate limiter
    if scraper.rate_limiter.is_blocked():
        # Rate limiter circuit is OPEN
        wait_time = scraper.rate_limiter.get_wait_time()
        logger.warning(f"[{request_id}] Rate limited, wait {wait_time}s")

        raise ScraperError(
            "Rate limited",
            error_type="rate_limited",
            status_code=429
        )
        # Returns: HTTP 429, message: "Too Many Requests"
```

**Rate Limiter State:**

```
consecutive_failures: 2
is_429: True (detected in last 5 seconds)
blocked_until: 2026-01-12 19:10:00
blocked: True  ← Blocks all requests
get_wait_time(): 2.3 seconds remaining
```

### Step 3: Validate Input

```python
    # STEP 3: Validate search query
    if len(q) < 2:
        logger.error(f"[{request_id}] Invalid query: too short")
        raise ScraperError(
            "Query must be at least 2 characters",
            error_type="invalid_input",
            status_code=400
        )
        # Returns: HTTP 400, message: "Invalid Input"
```

### Step 4: Check Cache

```python
    # STEP 4: Check if we already have this search result cached
    cache_key = f"search_{q}_{limit}"

    if cache_key in scraper.cache:
        cached_entry = scraper.cache[cache_key]
        cached_data = cached_entry['data']
        cached_time = cached_entry['timestamp']

        # Check if cache is still fresh (< 1 hour old)
        if time.time() - cached_time < 3600:
            logger.debug(f"[{request_id}] Cache hit")
            # Returns cached data immediately, no API call needed!
            return {
                "success": True,
                "results": cached_data
            }
        else:
            # Cache expired, delete it
            del scraper.cache[cache_key]
            logger.debug(f"[{request_id}] Cache expired")
```

### Step 5: Call Scraper to Search

```python
    # STEP 5: Cache miss, call scraper
    logger.debug(f"[{request_id}] Cache miss, fetching from Instagram")

    results = scraper.search_users(q=q, limit=limit)

    # If we reach here, scraper returned results (or None on error)
```

### Step 6: Inside Scraper - Prepare GraphQL Request

```python
# scraper.py - search_users() method
def search_users(self, q: str, limit: int = 10):
    logger.debug(f"search_users called with q={q}, limit={limit}")

    # STEP 6A: Wait before making request (avoid detection)
    self._random_delay()  # Sleep 1-3 seconds
    # Log: "2026-01-12 19:09:13 - scraper - DEBUG - [_random_delay:120] - delay: 1.23s"

    # STEP 6B: Prepare GraphQL query
    # The actual GraphQL query (a long string):
    query = """
    query XLS_SearchSurface($surface:XLSSearchSurfaceType!, $query_surface:XLSSearchSurfaceType!, $raw_query:String!, $count:Int!) {
      xls_search_surface(surface: $surface, query_surface: $query_surface, raw_query: $raw_query, count: $count) {
        search_surface {
          edges {
            node {
              __typename
              id
              username
              full_name
              is_verified
              profile_pic_url
              is_private
            }
          }
        }
      }
    }
    """

    # STEP 6C: Prepare variables
    variables = {
        "surface": "SEARCH",
        "query_surface": "SEARCH_WEB",
        "raw_query": "musk",
        "count": 5
    }

    # STEP 6D: Call GraphQL endpoint with retry logic
    response_data = self._post_graphql(
        doc_id="24146980661639222",  # Search document ID
        variables=variables
    )

    if response_data is None:
        logger.error("GraphQL search returned None")
        return None
```

### Step 7: Inside \_post_graphql - Retry Loop

```python
# scraper.py - _post_graphql() method
def _post_graphql(self, doc_id: str, variables: dict):
    logger.debug(f"_post_graphql called with doc_id={doc_id}")

    # STEP 7A: Pre-check if we're rate limited
    if self.rate_limiter.is_blocked():
        logger.error("Rate limiter blocked, returning None")
        return None

    # STEP 7B: Start retry loop
    for attempt in range(MAX_RETRIES):  # MAX_RETRIES = 3
        logger.debug(f"[attempt {attempt + 1}/{MAX_RETRIES}] Starting")

        try:
            # STEP 7C: Build request payload
            payload = {
                "query_string": query,      # Long GraphQL query
                "variables": variables,     # {"surface": "SEARCH", ...}
                "doc_id": doc_id,          # "24146980661639222"
                "query_hash": hash_value   # Computed hash of query
            }

            # Log request details
            logger.debug(f"[attempt {attempt + 1}] Payload prepared, size: {len(json.dumps(payload))} bytes")
```

### Step 8: Build HTTP Headers

```python
            # STEP 8A: Prepare headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "X-CSRFToken": self.csrf_token,  # "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
                "X-IG-App-ID": "936619743392459",
                "X-ASBD-ID": "359341",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.instagram.com/",
                "Origin": "https://www.instagram.com",
            }

            logger.debug(f"[attempt {attempt + 1}] Headers prepared")

            # The session.cookies automatically include:
            # Cookie: sessionid=abc123def456; csrftoken=xyz789; ds_user_id=9876543; mid=ABCD1234
```

### Step 9: Make HTTP POST Request

```python
            # STEP 9A: Make the actual HTTP request
            logger.debug(f"[attempt {attempt + 1}] Sending POST to instagram.com/graphql")

            response = self.session.post(
                url="https://www.instagram.com/graphql/",
                data=payload,  # Form data (not JSON)
                headers=headers,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)  # (5, 10) seconds
            )

            # STEP 9B: Log response status
            logger.debug(f"[attempt {attempt + 1}] Got response, status={response.status_code}")
```

### Step 10: Analyze Response Status

```python
            # STEP 10A: Success case
            if response.status_code == 200:
                logger.debug(f"[attempt {attempt + 1}] Status 200, parsing JSON")

                data = response.json()  # Parse JSON response
                logger.debug(f"[attempt {attempt + 1}] JSON parsed successfully")

                # Log success and update rate limiter
                self.rate_limiter.record_success()

                return data  # Return parsed JSON to caller

            # STEP 10B: Rate limit (429)
            elif response.status_code == 429:
                logger.info(f"[attempt {attempt + 1}] Got 429 Too Many Requests")

                # Extract wait time from header
                retry_after = response.headers.get('Retry-After', '60')
                logger.info(f"[attempt {attempt + 1}] Instagram says wait {retry_after}s")

                # Update rate limiter
                self.rate_limiter.record_rate_limit()

                # Calculate our own wait (exponential backoff)
                wait_time = (RETRY_BACKOFF_BASE ** attempt) + random.uniform(0, 1)
                logger.info(f"[attempt {attempt + 1}] Waiting {wait_time:.2f}s before retry")

                # Check if we have more attempts
                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait_time)
                    continue  # Jump to next iteration of for loop
                else:
                    logger.error("Max retries exhausted for 429")
                    return None

            # STEP 10C: Auth failure (401/403)
            elif response.status_code in [401, 403]:
                logger.warning(f"[attempt {attempt + 1}] Got {response.status_code} Unauthorized")
                logger.warning(f"[attempt {attempt + 1}] CSRF token expired, refreshing session")

                # Refresh CSRF token
                self._init_session()

                # Wait a bit and retry
                wait_time = 2 + random.uniform(0, 1)
                logger.info(f"[attempt {attempt + 1}] Waiting {wait_time:.2f}s before retry")

                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait_time)
                    continue  # Retry with new CSRF token
                else:
                    logger.error("Max retries exhausted for 401/403")
                    return None

            # STEP 10D: Server error (5xx)
            elif 500 <= response.status_code < 600:
                logger.error(f"[attempt {attempt + 1}] Got {response.status_code} Server Error")

                # Update rate limiter
                self.rate_limiter.record_http_error(response.status_code)

                # Calculate exponential backoff
                wait_time = min((RETRY_BACKOFF_BASE ** attempt) + random.uniform(0, 1), 3600)
                logger.info(f"[attempt {attempt + 1}] Waiting {wait_time:.2f}s before retry")

                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("Max retries exhausted for 5xx")
                    return None

            # STEP 10E: Other errors
            else:
                logger.error(f"[attempt {attempt + 1}] Unexpected status {response.status_code}")
                return None

        # STEP 11: Handle exceptions (network errors, timeouts)
        except requests.exceptions.Timeout:
            logger.warning(f"[attempt {attempt + 1}] Timeout waiting for response")

            if attempt < MAX_RETRIES - 1:
                wait_time = (RETRY_BACKOFF_BASE ** attempt) + random.uniform(0, 1)
                logger.info(f"[attempt {attempt + 1}] Waiting {wait_time:.2f}s before retry")
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries exhausted for timeout")
                return None

        except json.JSONDecodeError:
            logger.error(f"[attempt {attempt + 1}] Response is not valid JSON")
            logger.debug(f"[attempt {attempt + 1}] Response text: {response.text[:200]}")

            if attempt < MAX_RETRIES - 1:
                time.sleep((RETRY_BACKOFF_BASE ** attempt) + random.uniform(0, 1))
                continue
            else:
                logger.error("Max retries exhausted for JSON decode error")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"[attempt {attempt + 1}] Network error: {type(e).__name__}: {str(e)}")

            if attempt < MAX_RETRIES - 1:
                time.sleep((RETRY_BACKOFF_BASE ** attempt) + random.uniform(0, 1))
                continue
            else:
                logger.error("Max retries exhausted for network error")
                return None

    logger.error("All retry attempts exhausted")
    return None
```

### Step 11: Parse GraphQL Response

```python
# Back in search_users()
# response_data now contains the JSON response

if response_data is None:
    logger.error("Failed to get search data from Instagram")
    return None

logger.debug("Parsing search response")

try:
    # Extract users from nested response structure
    # Response structure:
    # {
    #   "data": {
    #     "xls_search_surface": {
    #       "search_surface": {
    #         "edges": [
    #           { "node": { "username": "muskankaria", ... } },
    #           ...
    #         ]
    #       }
    #     }
    #   }
    # }

    search_surface = response_data['data']['xls_search_surface']['search_surface']
    edges = search_surface['edges']

    logger.debug(f"Found {len(edges)} results")

    # STEP 11A: Extract user data from each result
    users = []
    for edge in edges:
        node = edge['node']

        user = {
            'username': node.get('username'),
            'full_name': node.get('full_name'),
            'is_verified': node.get('is_verified', False),
            'follower_count': node.get('follower_count', 0),
            'profile_pic': node.get('profile_pic_url'),
            'is_private': node.get('is_private', False)
        }

        users.append(user)
        logger.debug(f"Extracted user: {user['username']}")

    logger.debug(f"Total users extracted: {len(users)}")

    return users

except (KeyError, IndexError) as e:
    logger.error(f"Failed to parse response structure: {str(e)}")
    return None
```

### Step 12: Back in API - Store in Cache

```python
# Back in main.py search_users()

# results is now the list of users (or None)
if results is None:
    logger.error(f"[{request_id}] Scraper returned None")
    raise ScraperError(
        "Failed to fetch search results from Instagram",
        error_type="upstream_error",
        status_code=502
    )

# STEP 12: Store results in cache
cache_key = f"search_{q}_{limit}"
scraper.cache[cache_key] = {
    'data': results,
    'timestamp': time.time()
}

logger.debug(f"[{request_id}] Stored {len(results)} results in cache")
```

### Step 13: Format Response

```python
# STEP 13: Format final response
response_data = {
    'success': True,
    'results': results
}

logger.info(f"[{request_id}] SEARCH completed with {len(results)} results")

return response_data
```

### Final Response to Client

```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "results": [
    {
      "username": "muskankaria",
      "full_name": "Muskan Karia",
      "is_verified": true,
      "follower_count": 1200,
      "profile_pic": "https://scontent-maa5-2.cdninstagram.com/...",
      "is_private": false
    },
    {
      "username": "mahak_jaiswal_27",
      "full_name": "🍭~muskan~🍭",
      "is_verified": false,
      "follower_count": 850,
      "profile_pic": "https://scontent-maa3-1.cdninstagram.com/...",
      "is_private": false
    },
    ...
  ]
}
```

---

## Part 5: Network Traffic Visualization

### Complete Request-Response Cycle

```
┌──────────────────────┐
│   Your Client        │
└──────────┬───────────┘
           │
           │ HTTP GET /search?q=musk&limit=5
           ▼
┌──────────────────────┐
│   FastAPI Server     │
│   (main.py)          │
└──────────┬───────────┘
           │
           │ Calls scraper.search_users()
           ▼
┌──────────────────────┐
│   Scraper Instance   │
│   (scraper.py)       │
└──────────┬───────────┘
           │
           │ POST /graphql/ with:
           │ - Payload (query, variables, doc_id)
           │ - Headers (X-CSRFToken, X-IG-App-ID, etc)
           │ - Cookies (sessionid, csrftoken, etc)
           ▼
┌──────────────────────┐
│  Instagram Servers   │
│  (www.instagram.com) │
└──────────┬───────────┘
           │
           │ HTTP 200 OK + JSON response
           │ (or 429, 401, 403, 5xx, timeout)
           ▼
┌──────────────────────┐
│   Parse Response     │
│   (retry if needed)  │
└──────────┬───────────┘
           │
           │ Extract users array
           ▼
┌──────────────────────┐
│   Cache Results      │
│   (in-memory dict)   │
└──────────┬───────────┘
           │
           │ Format JSON response
           ▼
┌──────────────────────┐
│   Return to Client   │
│   (HTTP 200 + JSON)  │
└──────────────────────┘
```

---

## Part 6: Complete Log Timeline

### Full Request Log for "search musk"

```
2026-01-12 19:09:13.451 - instagram_scraper.api - INFO - [search_users:45] - [78bf3c7d] SEARCH q=musk, limit=5
2026-01-12 19:09:13.452 - instagram_scraper.api - DEBUG - [search_users:47] - [78bf3c7d] rate_limiter.is_blocked()=False
2026-01-12 19:09:13.453 - instagram_scraper.api - DEBUG - [search_users:51] - [78bf3c7d] Input validated
2026-01-12 19:09:13.454 - instagram_scraper.api - DEBUG - [search_users:56] - [78bf3c7d] Cache key: search_musk_5
2026-01-12 19:09:13.455 - instagram_scraper.api - DEBUG - [search_users:57] - [78bf3c7d] Cache miss
2026-01-12 19:09:13.456 - instagram_scraper.api - DEBUG - [search_users:60] - [78bf3c7d] Calling scraper.search_users()

2026-01-12 19:09:13.457 - instagram_scraper.scraper - DEBUG - [search_users:310] - [78bf3c7d] search_users(q=musk, limit=5)
2026-01-12 19:09:13.458 - instagram_scraper.scraper - DEBUG - [_random_delay:105] - [78bf3c7d] delay: 1.23s
2026-01-12 19:09:14.687 - instagram_scraper.scraper - DEBUG - [_random_delay:107] - [78bf3c7d] delay completed

2026-01-12 19:09:14.688 - instagram_scraper.scraper - DEBUG - [_post_graphql:180] - [78bf3c7d] _post_graphql doc_id=24146980661639222
2026-01-12 19:09:14.689 - instagram_scraper.scraper - DEBUG - [_post_graphql:182] - [78bf3c7d] pre-check rate_limiter.is_blocked()=False

2026-01-12 19:09:14.690 - instagram_scraper.scraper - DEBUG - [_post_graphql:186] - [78bf3c7d] [attempt 1/3] Building payload
2026-01-12 19:09:14.692 - instagram_scraper.scraper - DEBUG - [_post_graphql:200] - [78bf3c7d] [attempt 1/3] Payload size: 8234 bytes

2026-01-12 19:09:14.693 - instagram_scraper.scraper - DEBUG - [_post_graphql:205] - [78bf3c7d] [attempt 1/3] Sending POST to instagram.com/graphql

2026-01-12 19:09:14.694 - requests.packages.urllib3 - DEBUG - [connectionpool.py:123] - Starting new HTTPS connection (1): www.instagram.com
2026-01-12 19:09:14.945 - requests.packages.urllib3 - DEBUG - [connectionpool.py:456] - "POST /graphql/ HTTP/1.1" 200 4521

2026-01-12 19:09:14.946 - instagram_scraper.scraper - DEBUG - [_post_graphql:208] - [78bf3c7d] [attempt 1/3] Got response status=200

2026-01-12 19:09:14.947 - instagram_scraper.scraper - DEBUG - [_post_graphql:210] - [78bf3c7d] [attempt 1/3] Parsing JSON response
2026-01-12 19:09:14.950 - instagram_scraper.scraper - DEBUG - [_post_graphql:212] - [78bf3c7d] [attempt 1/3] JSON parsed successfully (4521 bytes)

2026-01-12 19:09:14.951 - instagram_scraper.rate_limiter - DEBUG - [record_success:85] - [78bf3c7d] Recording success, resetting consecutive_failures
2026-01-12 19:09:14.952 - instagram_scraper.scraper - DEBUG - [_post_graphql:214] - [78bf3c7d] [attempt 1/3] Returning parsed data

2026-01-12 19:09:14.953 - instagram_scraper.scraper - DEBUG - [search_users:340] - [78bf3c7d] Got response from GraphQL
2026-01-12 19:09:14.954 - instagram_scraper.scraper - DEBUG - [search_users:348] - [78bf3c7d] Extracting users from response
2026-01-12 19:09:14.955 - instagram_scraper.scraper - DEBUG - [search_users:350] - [78bf3c7d] Found edges: 5
2026-01-12 19:09:14.956 - instagram_scraper.scraper - DEBUG - [search_users:357] - [78bf3c7d] Extracted: muskankaria
2026-01-12 19:09:14.957 - instagram_scraper.scraper - DEBUG - [search_users:357] - [78bf3c7d] Extracted: mahak_jaiswal_27
2026-01-12 19:09:14.958 - instagram_scraper.scraper - DEBUG - [search_users:357] - [78bf3c7d] Extracted: muskan_aasef
2026-01-12 19:09:14.959 - instagram_scraper.scraper - DEBUG - [search_users:357] - [78bf3c7d] Extracted: muskansharma.5
2026-01-12 19:09:14.960 - instagram_scraper.scraper - DEBUG - [search_users:357] - [78bf3c7d] Extracted: mussu___lly
2026-01-12 19:09:14.961 - instagram_scraper.scraper - DEBUG - [search_users:365] - [78bf3c7d] Total users extracted: 5

2026-01-12 19:09:14.962 - instagram_scraper.api - DEBUG - [search_users:70] - [78bf3c7d] Got results from scraper
2026-01-12 19:09:14.963 - instagram_scraper.api - DEBUG - [search_users:75] - [78bf3c7d] Storing in cache with key=search_musk_5

2026-01-12 19:09:14.964 - instagram_scraper.api - INFO - [search_users:81] - [78bf3c7d] SEARCH completed with 5 results

INFO:     127.0.0.1:50486 - "GET /search?q=musk&limit=5 HTTP/1.1" 200 OK
```

---

## Part 7: What Happens When Things Go Wrong

### Scenario 1: Rate Limited (429)

```
2026-01-12 19:09:20.100 - [req123] SEARCH q=taylor, limit=5
2026-01-12 19:09:20.102 - [req123] Cache miss
2026-01-12 19:09:21.500 - [req123] [attempt 1/3] Sending POST to instagram.com/graphql
2026-01-12 19:09:21.750 - [req123] [attempt 1/3] Got response status=429
2026-01-12 19:09:21.751 - [req123] [attempt 1/3] Got 429 Too Many Requests
2026-01-12 19:09:21.752 - [req123] rate_limiter.record_rate_limit() - blocked=True, wait_until=19:09:23.75
2026-01-12 19:09:21.753 - [req123] [attempt 1/3] Waiting 2.05s before retry
2026-01-12 19:09:23.800 - [req123] [attempt 2/3] Sending POST to instagram.com/graphql
2026-01-12 19:09:24.050 - [req123] [attempt 2/3] Got response status=429
2026-01-12 19:09:24.051 - [req123] [attempt 2/3] Got 429 Too Many Requests
2026-01-12 19:09:24.052 - [req123] [attempt 2/3] Waiting 4.15s before retry
2026-01-12 19:09:28.200 - [req123] [attempt 3/3] Sending POST to instagram.com/graphql
2026-01-12 19:09:28.450 - [req123] [attempt 3/3] Got response status=429
2026-01-12 19:09:28.451 - [req123] [attempt 3/3] Got 429 Too Many Requests
2026-01-12 19:09:28.452 - [req123] Max retries exhausted for 429
2026-01-12 19:09:28.453 - [req123] Returning None to main
2026-01-12 19:09:28.454 - [req123] ERROR: Upstream error
HTTP/1.1 502 Bad Gateway
{
  "error": "Failed to fetch search results from Instagram",
  "error_type": "upstream_error"
}
```

### Scenario 2: CSRF Token Expired (401)

```
2026-01-12 19:10:00.100 - [req456] SEARCH q=music, limit=5
2026-01-12 19:10:00.300 - [req456] [attempt 1/3] Sending POST
2026-01-12 19:10:00.550 - [req456] [attempt 1/3] Got response status=401
2026-01-12 19:10:00.551 - [req456] [attempt 1/3] Got 401 Unauthorized
2026-01-12 19:10:00.552 - [req456] [attempt 1/3] CSRF token expired, calling _init_session()

  ↓ Inside _init_session():
  2026-01-12 19:10:00.553 - [req456] Initializing session, fetching CSRF token
  2026-01-12 19:10:00.554 - [req456] GET / request to instagram.com
  2026-01-12 19:10:00.800 - [req456] Got response status=200
  2026-01-12 19:10:00.801 - [req456] Parsed HTML response
  2026-01-12 19:10:00.850 - [req456] Extracted CSRF token: AbCdEfGhIj...
  2026-01-12 19:10:00.851 - [req456] Session initialized successfully
  ↑

2026-01-12 19:10:00.852 - [req456] [attempt 1/3] New CSRF token obtained
2026-01-12 19:10:00.853 - [req456] [attempt 1/3] Waiting 2.34s before retry
2026-01-12 19:10:03.200 - [req456] [attempt 2/3] Sending POST
2026-01-12 19:10:03.450 - [req456] [attempt 2/3] Got response status=200
2026-01-12 19:10:03.451 - [req456] [attempt 2/3] JSON parsed successfully
2026-01-12 19:10:03.500 - [req456] SEARCH completed with 10 results
HTTP/1.1 200 OK
{
  "success": true,
  "results": [...]
}
```

### Scenario 3: Network Timeout

```
2026-01-12 19:11:00.100 - [req789] SEARCH q=python, limit=5
2026-01-12 19:11:00.300 - [req789] [attempt 1/3] Sending POST (timeout=5s connect, 10s read)
2026-01-12 19:11:10.500 - [req789] [attempt 1/3] TIMEOUT: No response after 10 seconds
2026-01-12 19:11:10.501 - [req789] [attempt 1/3] Waiting 1.45s before retry
2026-01-12 19:11:11.950 - [req789] [attempt 2/3] Sending POST
2026-01-12 19:11:22.200 - [req789] [attempt 2/3] TIMEOUT again
2026-01-12 19:11:22.201 - [req789] [attempt 2/3] Waiting 3.67s before retry
2026-01-12 19:11:25.900 - [req789] [attempt 3/3] Sending POST
2026-01-12 19:11:36.100 - [req789] [attempt 3/3] TIMEOUT again
2026-01-12 19:11:36.101 - [req789] Max retries exhausted for timeout
HTTP/1.1 502 Bad Gateway
{
  "error": "Service temporarily unavailable",
  "error_type": "upstream_error"
}
```

---

## Part 8: Session Persistence Across Requests

### Request 1: Search for "musk"

```
Session state at start:
├── sessionid: [none]
├── csrftoken: [none]
└── is_initialized: False

During request:
├── _init_session() called
├── sessionid set from Set-Cookie header
├── csrftoken set from HTML extraction
└── is_initialized: True

Session state at end:
├── sessionid: abc123def456 (PERSISTENT)
├── csrftoken: XyzAbcDef789 (PERSISTENT)
└── is_initialized: True
```

### Request 2: Search for "taylor" (1 second later)

```
Session state at start:
├── sessionid: abc123def456 (REUSED - still valid!)
├── csrftoken: XyzAbcDef789 (REUSED - still valid!)
└── is_initialized: True

During request:
├── _init_session() NOT called (already initialized)
├── Cookies sent with request: sessionid=abc123def456; csrftoken=XyzAbcDef789
└── Instagram: "I recognize you, here's the data"

Session state at end:
├── sessionid: abc123def456 (unchanged)
├── csrftoken: XyzAbcDef789 (unchanged)
└── is_initialized: True
```

### Request 3: Search (after 1 hour, session might expire)

```
Session state at start:
├── sessionid: abc123def456 (EXPIRED)
├── csrftoken: XyzAbcDef789 (might be expired)
└── is_initialized: True (but tokens are stale)

During request:
├── POST with old sessionid and csrftoken
├── Instagram: "This token is expired, 401 Unauthorized"
├── _init_session() called to refresh
├── New sessionid: def456ghi789 (from Set-Cookie)
├── New csrftoken: JklMnoPqr890 (from HTML)
└── Retry POST with new tokens

Session state at end:
├── sessionid: def456ghi789 (UPDATED)
├── csrftoken: JklMnoPqr890 (UPDATED)
└── is_initialized: True
```

---

## Part 9: Rate Limiter Detailed State Transitions

### Initial State

```
RateLimitTracker:
├── consecutive_failures: 0
├── failure_count: 0
├── failure_times: []
├── error_codes: {}
├── blocked: False
├── blocked_until: None
└── last_success_time: None
```

### After 1st Success

```
record_success() called
├── consecutive_failures: 0 (already 0)
├── last_success_time: 2026-01-12 19:09:14.951
└── Result: No blocking, request allowed
```

### After 1st Failure (429)

```
record_rate_limit() called (429 Too Many Requests)
├── consecutive_failures: 1
├── failure_count: 1
├── failure_times: [2026-01-12 19:09:21.750]
├── error_codes: {"429": 1}
├── blocked: False (not yet, only 1 failure)
├── blocked_until: None
└── Result: Allow request, but tracked
```

### After 3rd Failure (all 429s)

```
record_rate_limit() called again (3rd time)
├── consecutive_failures: 3
├── failure_count: 3
├── failure_times: [19:09:21, 19:09:24, 19:09:28]
├── error_codes: {"429": 3}
├── blocked: True (≥ CIRCUIT_BREAKER_THRESHOLD of 5? No)
├── blocked_until: None
└── Result: Still allow (not yet at threshold)

Wait, actually checking threshold (default 5):
├── Need 5 failures to trigger blocking
└── Currently at 3, so still allowed
```

### After 5th Failure (Threshold Reached)

```
record_rate_limit() called (5th time)
├── consecutive_failures: 5
├── failure_count: 5
├── failure_times: [19:09:21, 19:09:24, 19:09:28, 19:09:35, 19:09:42]
├── error_codes: {"429": 5}
├── blocked: True (≥ 5, THRESHOLD TRIGGERED)
├── blocked_until: 2026-01-12 19:09:42 + exponential_wait
│   └── wait = min(2^(5-1) + random, 3600) = min(16 + 0.5, 3600) = 16.5s
│   └── blocked_until = 19:09:42 + 16.5 = 19:09:58.5
└── Result: START BLOCKING ALL REQUESTS
```

### Blocking Active (is_blocked() = True)

```
Next request during blocking period:
├── is_blocked() checked: returns True
├── get_wait_time() returns: max(0, 19:09:58.5 - now) = 3.2s remaining
├── Request rejected immediately
└── Return: HTTP 429 "Rate Limited, retry after 3.2s"
```

### Recovery After Blocking Expires

```
Time: 2026-01-12 19:09:59.0 (blocking period over)

Next request after block expires:
├── is_blocked() checked: blocked_until expired, returns False
├── Blocking released, allow request to proceed
├── POST to Instagram succeeds: status 200
├── record_success() called
│   └── consecutive_failures: 0 (RESET)
│   └── blocked: False
│   └── blocked_until: None
└── Back to normal state
```

---

## Part 10: Cookie Lifecycle Example

### Initial State (No Cookies)

```
When server starts:
self.session = requests.Session()
# Cookie jar is empty
```

### After \_init_session()

```
GET https://www.instagram.com/

Response headers include:
Set-Cookie: sessionid=rnd12345678901234567890ab; Path=/; Domain=.instagram.com
Set-Cookie: csrftoken=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890; Path=/
Set-Cookie: mid=ZaBcDeF1234567890abcdef; Path=/; Expires=Wed, 12 Jan 2027
Set-Cookie: ig_nrcb=1; Path=/; Expires=Tue, 12 Jan 2027
Set-Cookie: ds_user_id=9876543; Path=/; Expires=Wed, 12 Jan 2027
Set-Cookie: datr=XyZaBcDeFgHiJkLmNoPqRsT; Path=/; Expires=Wed, 12 Jan 2027

Session.cookies (in-memory storage):
├── sessionid: rnd12345678901234567890ab (Session: expires when browser closes)
├── csrftoken: AbCdEfGhIjKlMnOpQrStUvWxYz1234567890 (Session)
├── mid: ZaBcDeF1234567890abcdef (Persistent: expires in 1 year)
├── ig_nrcb: 1 (Persistent: expires in 1 year)
├── ds_user_id: 9876543 (Persistent: expires in 1 year)
└── datr: XyZaBcDeFgHiJkLmNoPqRsT (Persistent: expires in 1 year)
```

### On Every Subsequent Request

```
POST https://www.instagram.com/graphql/

Our request automatically includes:
Cookie: sessionid=rnd12345678901234567890ab; csrftoken=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890; mid=ZaBcDeF1234567890abcdef; ig_nrcb=1; ds_user_id=9876543; datr=XyZaBcDeFgHiJkLmNoPqRsT

(requests.Session automatically manages this!)
```

### If Session Expires (After 1 Week)

```
POST https://www.instagram.com/graphql/

Instagram sees:
Cookie: sessionid=rnd12345678901234567890ab (expired!)

Instagram response:
HTTP/1.1 401 Unauthorized

Our code:
├── Detects 401 status
├── Calls _init_session() to get new sessionid
├── Retries POST with new sessionid
└── Request succeeds
```

---

## Summary: Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. CLIENT REQUEST                                                      │
│     GET /search?q=musk&limit=5                                          │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────────┐
│  2. API INITIALIZATION                                                  │
│     ├── Generate request_id = "78bf3c7d"                                │
│     ├── Check rate limiter (is_blocked? NO)                             │
│     ├── Validate input (len >= 2? YES)                                  │
│     └── Check cache ("search_musk_5" exists? NO)                        │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────────┐
│  3. SCRAPER INITIALIZATION (First Time Only)                            │
│     ├── Create session = requests.Session()                             │
│     ├── GET / from instagram.com                                        │
│     ├── Instagram sends Set-Cookie headers                              │
│     ├── Session stores cookies in memory                                │
│     └── Extract CSRF token from HTML = "AbCdEfGhIj..."                 │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────────┐
│  4. BUILD GRAPHQL REQUEST                                               │
│     ├── Query: "query XLS_SearchSurface(...) { ... }"                   │
│     ├── Variables: {"raw_query": "musk", "count": 5, ...}               │
│     ├── Payload form data (8KB+)                                        │
│     └── Headers:                                                         │
│         ├── X-CSRFToken: AbCdEfGhIj...                                  │
│         ├── X-IG-App-ID: 936619743392459                                │
│         └── (+ cookies from session)                                     │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────────┐
│  5. NETWORK REQUEST (Retry Loop: up to 3 attempts)                      │
│     ├── POST /graphql/ to instagram.com                                 │
│     ├── timeout: (5s connect, 10s read)                                 │
│     │                                                                    │
│     │ Response:                                                          │
│     │ ├── 200 OK? → Parse JSON, return data                             │
│     │ ├── 429? → Wait 2^attempt sec, retry                              │
│     │ ├── 401/403? → Refresh CSRF, retry                                │
│     │ ├── 5xx? → Wait 2^failures sec, retry                             │
│     │ ├── Timeout? → Wait 2^attempt sec, retry                          │
│     │ └── JSON Error? → Wait, retry                                     │
│     │                                                                    │
│     └── All 3 attempts failed? → Return None                            │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────────┐
│  6. PARSE RESPONSE                                                      │
│     ├── Extract from: data['data']['xls_search_surface'][...]           │
│     ├── For each edge in results:                                       │
│     │   └── {username, full_name, is_verified, follower_count, ...}     │
│     └── Return list of 5 users                                          │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────────┐
│  7. CACHE & RETURN                                                      │
│     ├── Store in cache["search_musk_5"]                                 │
│     ├── Format final JSON response                                      │
│     ├── Log: "SEARCH completed with 5 results"                          │
│     └── Return HTTP 200 + JSON                                          │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────────┐
│  8. CLIENT RESPONSE                                                     │
│     HTTP/1.1 200 OK                                                     │
│     {                                                                   │
│       "success": true,                                                  │
│       "results": [                                                      │
│         {                                                               │
│           "username": "muskankaria",                                    │
│           "full_name": "Muskan Karia",                                  │
│           "is_verified": true,                                          │
│           "follower_count": 1200,                                       │
│           "profile_pic": "https://...",                                 │
│           "is_private": false                                           │
│         },                                                              │
│         ...                                                             │
│       ]                                                                 │
│     }                                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

This comprehensive guide covers every technical detail from the initial cookie/token setup through the complete request-response cycle, including error handling and recovery mechanisms.
