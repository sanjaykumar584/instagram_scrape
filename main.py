from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from scraper import InstagramScraper
from cache import SimpleCache
import time

app = FastAPI(title="Instagram Scraper API")
scraper = InstagramScraper()
cache = SimpleCache(ttl=None)  # TTL from env or default
start_time = time.time()

@app.get("/search")
async def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(20, ge=1, le=50)
):
    """Search Instagram users"""
    try:
        cache_key = f"search:{q}:{limit}"
        cached = cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        results = scraper.search_users(q, limit)
        response = {
            "success": True,
            "results": results,
            "count": len(results)
        }
        cache.set(cache_key, response)
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile/{username}")
async def get_profile(
    username: str,
    posts: int = Query(0, ge=0, le=50)
):
    """Get Instagram profile details"""
    try:
        cache_key = f"profile:{username}:{posts}"
        cached = cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        profile_data = scraper.get_profile(username, include_posts=posts > 0, post_limit=posts)
        if not profile_data:
            raise HTTPException(status_code=404, detail=f"Profile '{username}' not found")

        response = {
            "success": True,
            "profile": profile_data["profile"],
            "posts": profile_data.get("posts", [])
        }
        cache.set(cache_key, response)
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "uptime": int(time.time() - start_time)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
