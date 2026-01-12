from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from instagrapi.exceptions import (
    LoginRequired,
    ChallengeRequired,
    PleaseWaitFewMinutes,
    ClientError,
)

from .instagram_client import service

app = FastAPI(title="Instagram Scraper API", version="0.1.0")


@app.on_event("startup")
def startup_event() -> None:
    service.maybe_login_on_startup()


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/search")
def search_users(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    try:
        results = service.search_users(q, limit)
        return {"query": q, "count": len(results), "results": results}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LoginRequired:
        raise HTTPException(status_code=401, detail="Instagram login required")
    except ChallengeRequired:
        raise HTTPException(status_code=403, detail="Instagram challenge required. Try again later or verify the account.")
    except PleaseWaitFewMinutes:
        raise HTTPException(status_code=429, detail="Rate limited by Instagram. Please wait a few minutes and retry.")
    except ClientError as e:
        raise HTTPException(status_code=502, detail=f"Instagram client error: {e}")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to search users")


@app.get("/profile/{username}")
def get_profile(username: str):
    try:
        profile = service.get_profile(username)
        if not profile.get("username"):
            raise HTTPException(status_code=404, detail="User not found")
        return profile
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LoginRequired:
        raise HTTPException(status_code=401, detail="Instagram login required")
    except ChallengeRequired:
        raise HTTPException(status_code=403, detail="Instagram challenge required. Try again later or verify the account.")
    except PleaseWaitFewMinutes:
        raise HTTPException(status_code=429, detail="Rate limited by Instagram. Please wait a few minutes and retry.")
    except ClientError as e:
        raise HTTPException(status_code=502, detail=f"Instagram client error: {e}")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")
