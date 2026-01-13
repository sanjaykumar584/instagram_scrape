import json
import time
from typing import Dict, List, Any

import httpx
from youtubesearchpython.core.requests import RequestCore
from youtubesearchpython.core.constants import ResultMode, userAgent

# Patch RequestCore at module import to fix httpx compatibility
def _patch_request_core() -> None:
    def _proxy_value(proxy: Dict[str, str]):
        return proxy if proxy else None

    def sync_post(self):
        return httpx.post(
            self.url,
            headers={"User-Agent": userAgent},
            json=self.data,
            timeout=self.timeout,
            proxy=_proxy_value(self.proxy),
        )

    async def async_post(self):
        async with httpx.AsyncClient(proxy=_proxy_value(self.proxy)) as client:
            return await client.post(
                self.url,
                headers={"User-Agent": userAgent},
                json=self.data,
                timeout=self.timeout,
            )

    def sync_get(self):
        return httpx.get(
            self.url,
            headers={"User-Agent": userAgent},
            timeout=self.timeout,
            cookies={"CONSENT": "YES+1"},
            proxy=_proxy_value(self.proxy),
        )

    async def async_get(self):
        async with httpx.AsyncClient(proxy=_proxy_value(self.proxy)) as client:
            return await client.get(
                self.url,
                headers={"User-Agent": userAgent},
                timeout=self.timeout,
                cookies={"CONSENT": "YES+1"},
            )

    RequestCore.syncPostRequest = sync_post
    RequestCore.asyncPostRequest = async_post
    RequestCore.syncGetRequest = sync_get
    RequestCore.asyncGetRequest = async_get

_patch_request_core()

# Import after patching
from youtubesearchpython import VideosSearch, ChannelsSearch, Playlist, Video
from youtubesearchpython.handlers import componenthandler

# Patch componenthandler to handle None channel IDs
def _patch_component_handler() -> None:
    original_get_video_component = componenthandler.ComponentHandler._getVideoComponent
    
    def patched_get_video_component(self, element, shelfTitle=None):
        # Manually extract component to avoid None concatenation error
        from youtubesearchpython.handlers.componenthandler import videoElementKey
        video = element.get(videoElementKey, {})
        
        component = {
            'type': 'video',
            'id': self._getValue(video, ['videoId']),
            'title': self._getValue(video, ['title', 'runs', 0, 'text']),
            'publishedTime': self._getValue(video, ['publishedTimeText', 'simpleText']),
            'duration': self._getValue(video, ['lengthText', 'simpleText']),
            'viewCount': {
                'text': self._getValue(video, ['viewCountText', 'simpleText']),
                'short': self._getValue(video, ['shortViewCountText', 'simpleText']),
            },
            'thumbnails': self._getValue(video, ['thumbnail', 'thumbnails']),
            'richThumbnail': self._getValue(video, ['richThumbnail', 'movingThumbnailRenderer', 'movingThumbnailDetails', 'thumbnails', 0]),
            'descriptionSnippet': self._getValue(video, ['detailedMetadataSnippets', 0, 'snippetText', 'runs']),
            'channel': {
                'name': self._getValue(video, ['ownerText', 'runs', 0, 'text']),
                'id': self._getValue(video, ['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']),
                'thumbnails': self._getValue(video, ['channelThumbnailSupportedRenderers', 'channelThumbnailWithLinkRenderer', 'thumbnail', 'thumbnails']),
            },
            'accessibility': {
                'title': self._getValue(video, ['title', 'accessibility', 'accessibilityData', 'label']),
                'duration': self._getValue(video, ['lengthText', 'accessibility', 'accessibilityData', 'label']),
            },
        }
        
        # Safely add links (handle None values)
        component['link'] = f"https://www.youtube.com/watch?v={component['id']}" if component['id'] else ""
        channel_id = component['channel']['id']
        component['channel']['link'] = f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""
        component['shelfTitle'] = shelfTitle
        
        return component
    
    componenthandler.ComponentHandler._getVideoComponent = patched_get_video_component

_patch_component_handler()


class SimpleCache:
    """A tiny in-memory TTL cache used to avoid redundant upstream calls."""

    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl
        self.cache: Dict[str, Any] = {}

    def get(self, key: str):
        if key in self.cache:
            value, expiry = self.cache[key]
            if time.time() < expiry:
                return value
            del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self.cache[key] = (value, time.time() + self.ttl)

    def size(self) -> int:
        return len(self.cache)


class YouTubeSearchClient:
    def __init__(self, cache_ttl: int = 300) -> None:
        self.cache = SimpleCache(ttl=cache_ttl)

    def _safe_dict_get(self, obj: Any, *keys: str, default: Any = "") -> Any:
        """Safely navigate nested dicts."""
        val = obj
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                return default
        return val if val is not None else default

    def _safe_get(self, obj: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields from obj using schema, handling both direct keys and callables."""
        result = {}
        for out_key, path in schema.items():
            try:
                if callable(path):
                    result[out_key] = path(obj)
                elif isinstance(path, str):
                    result[out_key] = obj.get(path, "") if isinstance(obj, dict) else ""
                else:
                    result[out_key] = ""
            except (AttributeError, TypeError, KeyError):
                result[out_key] = ""
        return result

        # Patch RequestCore to use httpx proxy parameter name (library uses deprecated 'proxies').
        self._patch_request_core()

    def _patch_request_core(self) -> None:
        def _proxy_value(proxy: Dict[str, str]):
            return proxy if proxy else None

        def sync_post(self):
            return httpx.post(
                self.url,
                headers={"User-Agent": userAgent},
                json=self.data,
                timeout=self.timeout,
                proxy=_proxy_value(self.proxy),
            )

        async def async_post(self):
            async with httpx.AsyncClient(proxy=_proxy_value(self.proxy)) as client:
                return await client.post(
                    self.url,
                    headers={"User-Agent": userAgent},
                    json=self.data,
                    timeout=self.timeout,
                )

        def sync_get(self):
            return httpx.get(
                self.url,
                headers={"User-Agent": userAgent},
                timeout=self.timeout,
                cookies={"CONSENT": "YES+1"},
                proxy=_proxy_value(self.proxy),
            )

        async def async_get(self):
            async with httpx.AsyncClient(proxy=_proxy_value(self.proxy)) as client:
                return await client.get(
                    self.url,
                    headers={"User-Agent": userAgent},
                    timeout=self.timeout,
                    cookies={"CONSENT": "YES+1"},
                )

        RequestCore.syncPostRequest = sync_post
        RequestCore.asyncPostRequest = async_post
        RequestCore.syncGetRequest = sync_get
        RequestCore.asyncGetRequest = async_get

    def _cache_or_fetch(self, key: str, fetch_fn):
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        data = fetch_fn()
        self.cache.set(key, data)
        return data

    def search_videos(self, query: str, limit: int = 10) -> Dict[str, Any]:
        def _fetch():
            search = VideosSearch(query, limit=limit)
            results = search.result() or {}
            if isinstance(results, str):
                try:
                    results = json.loads(results)
                except Exception:
                    results = {}
            videos: List[Dict[str, Any]] = []
            for video in results.get("result", []):
                videos.append(self._safe_get(video, {
                    "id": "id",
                    "title": "title",
                    "duration": "duration",
                    "views": lambda v: v.get("viewCount", {}).get("text", "0") if isinstance(v.get("viewCount"), dict) else "0",
                    "channel": lambda v: v.get("channel", {}).get("name", "") if isinstance(v.get("channel"), dict) else "",
                    "channel_id": lambda v: v.get("channel", {}).get("id", "") if isinstance(v.get("channel"), dict) else "",
                    "thumbnail": lambda v: (v.get("thumbnails", [{}])[0] or {}).get("url", "") if v.get("thumbnails") else "",
                    "published_time": "publishedTime",
                    "link": "link",
                    "description": lambda v: (v.get("descriptionSnippet", [{}])[0] or {}).get("text", "") if v.get("descriptionSnippet") else "",
                }))

            return {
                "success": True,
                "query": query,
                "total_results": len(videos),
                "videos": videos,
            }

        key = f"videos:{query}:{limit}"
        return self._cache_or_fetch(key, _fetch)

    def get_video(self, video_id: str) -> Dict[str, Any]:
        def _fetch():
            info = Video.getInfo(f"https://www.youtube.com/watch?v={video_id}") or {}
            if not info:
                raise ValueError("Video not found")
            return {
                "success": True,
                "video": {
                    "id": video_id,
                    "title": info.get("title", ""),
                    "description": info.get("description", ""),
                    "duration": info.get("duration", {}).get("secondsText", ""),
                    "views": info.get("viewCount", {}).get("text", "0"),
                    "likes": info.get("likes", {}).get("text", "N/A"),
                    "channel": {
                        "name": info.get("channel", {}).get("name", ""),
                        "id": info.get("channel", {}).get("id", ""),
                        "subscribers": info.get("channel", {}).get("subscribers", {}).get("simpleText", "N/A"),
                    },
                    "published_date": info.get("publishDate", ""),
                    "thumbnails": info.get("thumbnails", []),
                    "keywords": info.get("keywords", []),
                    "category": info.get("category", ""),
                    "is_live": info.get("isLiveContent", False),
                    "link": f"https://www.youtube.com/watch?v={video_id}",
                },
            }

        key = f"video:{video_id}"
        return self._cache_or_fetch(key, _fetch)

    def search_shorts(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for YouTube Shorts (videos under 60 seconds)."""
        def _fetch():
            try:
                # Fetch significantly more videos since shorts are much rarer than regular videos
                search = VideosSearch(query, limit=limit * 10)
            except (TypeError, AttributeError, KeyError):
                # If search fails, try with fewer limit
                try:
                    search = VideosSearch(query, limit=limit)
                except Exception:
                    return {
                        "success": False,
                        "query": query,
                        "total_results": 0,
                        "shorts": [],
                    }
            
            results = search.result() or {}
            if isinstance(results, str):
                try:
                    results = json.loads(results)
                except Exception:
                    results = {}
            
            shorts: List[Dict[str, Any]] = []
            for video in results.get("result", []):
                # Filter for shorts: typically under 60 seconds
                duration_str = video.get("duration", "")
                is_short = self._is_short_duration(duration_str)
                
                if is_short:
                    shorts.append(self._safe_get(video, {
                        "id": "id",
                        "title": "title",
                        "duration": "duration",
                        "views": lambda v: v.get("viewCount", {}).get("text", "0") if isinstance(v.get("viewCount"), dict) else "0",
                        "channel": lambda v: v.get("channel", {}).get("name", "") if isinstance(v.get("channel"), dict) else "",
                        "channel_id": lambda v: v.get("channel", {}).get("id", "") if isinstance(v.get("channel"), dict) else "",
                        "thumbnail": lambda v: (v.get("thumbnails", [{}])[0] or {}).get("url", "") if v.get("thumbnails") else "",
                        "published_time": "publishedTime",
                        "link": "link",
                        "description": lambda v: (v.get("descriptionSnippet", [{}])[0] or {}).get("text", "") if v.get("descriptionSnippet") else "",
                    }))
                    
                    if len(shorts) >= limit:
                        break

            return {
                "success": True,
                "query": query,
                "total_results": len(shorts),
                "shorts": shorts,
            }

        key = f"shorts:{query}:{limit}"
        return self._cache_or_fetch(key, _fetch)

    def _is_short_duration(self, duration_str: str) -> bool:
        """Check if duration string indicates a true YouTube Short (< 60 seconds total).
        
        YouTube Shorts are only videos with duration in format 0:XX (0-59 seconds).
        Rejects:
        - Videos with 1+ minutes duration (1:XX, 10:XX, etc.)
        - HH:MM:SS format (long videos)
        - Empty/None/invalid formats
        """
        if not duration_str:
            return False
        
        duration_str = str(duration_str).strip()
        parts = duration_str.split(":")
        
        try:
            if len(parts) == 2:  # MM:SS format
                minutes = int(parts[0])
                seconds = int(parts[1])
                
                # Only 0:XX format qualifies as a short (< 60 seconds total)
                # Reject any video with 1+ minutes of duration
                if minutes == 0 and 0 <= seconds < 60:
                    return True
                return False
                    
            elif len(parts) == 3:  # HH:MM:SS format - definitely not a short
                return False
            else:
                # Unknown format - safer to exclude
                return False
                
        except (ValueError, IndexError, AttributeError):
            # If parsing fails, definitely not a short
            return False

    def search_channels(self, query: str, limit: int = 10) -> Dict[str, Any]:
        def _fetch():
            search = ChannelsSearch(query, limit=limit)
            results = search.result() or {}
            if isinstance(results, str):
                try:
                    results = json.loads(results)
                except Exception:
                    results = {}
            channels: List[Dict[str, Any]] = []
            for channel in results.get("result", []):
                channels.append(self._safe_get(channel, {
                    "id": "id",
                    "title": "title",
                    "subscribers": lambda c: self._safe_dict_get(c, "subscribers", "simpleText", default="N/A"),
                    "video_count": "videoCount",
                    "description": lambda c: (c.get("descriptionSnippet", [{}])[0] or {}).get("text", "") if c.get("descriptionSnippet") else "",
                    "thumbnail": lambda c: (c.get("thumbnails", [{}])[0] or {}).get("url", "") if c.get("thumbnails") else "",
                    "link": "link",
                }))

            return {
                "success": True,
                "query": query,
                "total_results": len(channels),
                "channels": channels,
            }

        key = f"channels:{query}:{limit}"
        return self._cache_or_fetch(key, _fetch)

    def get_playlist(self, playlist_id: str, limit: int = 50) -> Dict[str, Any]:
        def _fetch():
            playlist = Playlist.get(
                f"https://www.youtube.com/playlist?list={playlist_id}",
                mode=ResultMode.dict,
            ) or {}
            if not playlist:
                raise ValueError("Playlist not found")

            videos: List[Dict[str, Any]] = []
            for video in playlist.get("videos", [])[:limit]:
                videos.append({
                    "id": video.get("id", ""),
                    "title": video.get("title", ""),
                    "duration": video.get("duration", ""),
                    "channel": video.get("channel", {}).get("name", ""),
                    "thumbnail": (video.get("thumbnails", [{}])[0] or {}).get("url", ""),
                    "link": video.get("link", ""),
                })

            return {
                "success": True,
                "playlist": {
                    "id": playlist_id,
                    "title": playlist.get("info", {}).get("title", ""),
                    "video_count": playlist.get("info", {}).get("videoCount", 0),
                    "views": playlist.get("info", {}).get("views", 0),
                    "channel": playlist.get("info", {}).get("channel", {}).get("name", ""),
                    "videos": videos,
                },
            }

        key = f"playlist:{playlist_id}:{limit}"
        return self._cache_or_fetch(key, _fetch)

    def get_channel_videos_message(self, channel_id: str, limit: int) -> Dict[str, Any]:
        # youtube-search-python does not support direct channel video listing without scraping
        return {
            "success": True,
            "message": "For channel videos, use the channel name in search endpoint",
            "example": f"/search/videos?q=channel_name&limit={limit}",
            "channel_id": channel_id,
        }

    def cache_size(self) -> int:
        return self.cache.size()
