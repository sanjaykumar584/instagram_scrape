from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from scraper import InstagramScraper
import time
import requests
import uuid
from logger_config import get_logger

logger = get_logger("api")

app = FastAPI(title="Instagram Scraper API")
scraper = InstagramScraper()
start_time = time.time()

class ScraperError(Exception):
    """Custom exception for scraper errors"""
    def __init__(self, error_type: str, message: str, status_code: int = 500):
        self.error_type = error_type
        self.message = message
        self.status_code = status_code

@app.exception_handler(ScraperError)
async def scraper_error_handler(request, exc):
    """Handle custom scraper errors"""
    logger.warning(f"ScraperError: {exc.error_type} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_type": exc.error_type,
            "message": exc.message
        }
    )

@app.get("/search")
async def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(20, ge=1, le=50)
):
    """Search Instagram users"""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] SEARCH q={q}, limit={limit}")
    
    try:
        # Check if rate limited
        if scraper.rate_limiter.is_blocked():
            wait = scraper.rate_limiter.get_wait_time()
            logger.warning(f"[{request_id}] Rate limited, wait {wait:.1f}s")
            raise ScraperError(
                error_type="rate_limited",
                message=f"Rate limited. Try again in {wait:.0f} seconds",
                status_code=429
            )
        
        results = scraper.search_users(q, limit)
        if results is None:
            raise ScraperError(
                error_type="upstream_error",
                message="Failed to fetch search results from Instagram",
                status_code=502
            )
        
        if not results:
            logger.warning(f"[{request_id}] No results found for search query")
        
        response = {
            "success": True,
            "results": results,
            "count": len(results)
        }
        logger.info(f"[{request_id}] SEARCH completed with {len(results)} results")
        return JSONResponse(content=response)
        
    except ScraperError:
        raise
    except Exception as e:
        logger.exception(f"[{request_id}] Unexpected error in search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/profile/{username}")
async def get_profile(
    username: str,
    posts: int = Query(0, ge=0, le=50)
):
    """Get Instagram profile details"""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] PROFILE username={username}, posts={posts}")
    
    try:
        # Validate username
        if not username or len(username) > 100:
            raise ScraperError(
                error_type="invalid_input",
                message="Invalid username",
                status_code=400
            )
        
        # Check if rate limited
        if scraper.rate_limiter.is_blocked():
            wait = scraper.rate_limiter.get_wait_time()
            logger.warning(f"[{request_id}] Rate limited, wait {wait:.1f}s")
            raise ScraperError(
                error_type="rate_limited",
                message=f"Rate limited. Try again in {wait:.0f} seconds",
                status_code=429
            )
        
        profile_data = scraper.get_profile(username, include_posts=posts > 0, post_limit=posts)
        if not profile_data:
            logger.warning(f"[{request_id}] Profile not found: {username}")
            raise ScraperError(
                error_type="not_found",
                message=f"Profile '{username}' not found or is private",
                status_code=404
            )

        response = {
            "success": True,
            "profile": profile_data["profile"],
            "posts": profile_data.get("posts", [])
        }
        logger.info(f"[{request_id}] PROFILE {username} completed with {len(response.get('posts', []))} posts")
        return JSONResponse(content=response)
        
    except ScraperError:
        raise
    except Exception as e:
        logger.exception(f"[{request_id}] Unexpected error in profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint with Instagram connectivity test"""
    try:
        # Test Instagram connectivity
        ig_reachable = False
        csrf_valid = False
        
        try:
            resp = requests.get("https://www.instagram.com", timeout=5)
            ig_reachable = resp.status_code == 200
        except Exception as e:
            logger.warning(f"Instagram connectivity check failed: {e}")
        
        if scraper.csrf_token:
            csrf_valid = True
        
        health_data = {
            "status": "ok" if (ig_reachable and csrf_valid) else "degraded",
            "uptime": int(time.time() - start_time),
            "instagram_reachable": ig_reachable,
            "csrf_token_valid": csrf_valid,
            "rate_limit_blocked": scraper.rate_limiter.is_blocked(),
            "consecutive_failures": scraper.rate_limiter.consecutive_failures,
        }
        
        if scraper.rate_limiter.is_blocked():
            health_data["rate_limit_wait_seconds"] = scraper.rate_limiter.get_wait_time()
        
        return health_data
        
    except Exception as e:
        logger.exception(f"Health check error: {e}")
        return {
            "status": "error",
            "uptime": int(time.time() - start_time),
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
