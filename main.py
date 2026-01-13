from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from scraper import InstagramScraper
from youtube_client import YouTubeSearchClient
import time
import requests
import uuid
from logger_config import get_logger

logger = get_logger("api")

app = FastAPI(title="Instagram Scraper API")
scraper = InstagramScraper()
yt_client = YouTubeSearchClient(cache_ttl=300)
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


@app.get("/search/videos")
async def search_videos(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
):
    """Search YouTube videos (unofficial)."""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] YT SEARCH q={q}, limit={limit}")
    try:
        response = yt_client.search_videos(q, limit)
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception(f"[{request_id}] YouTube search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@app.get("/search/shorts")
async def search_shorts(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
):
    """Search YouTube Shorts - short-form videos under 60 seconds (unofficial)."""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] YT SHORTS q={q}, limit={limit}")
    try:
        response = yt_client.search_shorts(q, limit)
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception(f"[{request_id}] YouTube shorts search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@app.get("/video/{video_id}")
async def get_video(video_id: str):
    """Get detailed information about a specific YouTube video."""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] YT VIDEO video_id={video_id}")
    try:
        response = yt_client.get_video(video_id)
        return JSONResponse(content=response)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    except Exception as e:
        logger.exception(f"[{request_id}] YouTube video error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video: {e}")


@app.get("/search/channels")
async def search_channels(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
):
    """Search YouTube channels (unofficial)."""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] YT CHANNELS q={q}, limit={limit}")
    try:
        response = yt_client.search_channels(q, limit)
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception(f"[{request_id}] YouTube channel search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@app.get("/playlist/{playlist_id}")
async def get_playlist(
    playlist_id: str,
    limit: int = Query(50, ge=1, le=100, description="Number of videos to fetch"),
):
    """Get videos from a YouTube playlist (unofficial)."""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] YT PLAYLIST playlist_id={playlist_id}, limit={limit}")
    try:
        response = yt_client.get_playlist(playlist_id, limit)
        return JSONResponse(content=response)
    except ValueError:
        raise HTTPException(status_code=404, detail="Playlist not found")
    except Exception as e:
        logger.exception(f"[{request_id}] YouTube playlist error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get playlist: {e}")


@app.get("/channel/{channel_id}/videos")
async def get_channel_videos(
    channel_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of videos"),
):
    """Placeholder guidance for fetching a channel's videos using search."""
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] YT CHANNEL VIDEOS channel_id={channel_id}, limit={limit}")
    try:
        response = yt_client.get_channel_videos_message(channel_id, limit)
        return JSONResponse(content=response)
    except Exception as e:
        logger.exception(f"[{request_id}] YouTube channel videos error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed: {e}")


@app.get("/trending")
async def get_trending(region: str = Query("US", description="Country code (US, IN, GB, etc.)")):
    """Placeholder endpoint for trending videos."""
    return JSONResponse(content={
        "success": False,
        "message": "Trending videos require official YouTube API or web scraping",
        "suggestion": "Use search with popular terms or specific channels",
        "region": region,
    })

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

        # YouTube subsystem health (best effort)
        health_data["youtube_cache_items"] = yt_client.cache_size()
        
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
