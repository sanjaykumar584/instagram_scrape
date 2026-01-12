import requests
import re
import json
import time
import random
from typing import Optional, Dict, List, Any
from bs4 import BeautifulSoup
import os

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10") or 10)
MIN_DELAY = float(os.getenv("MIN_DELAY", "1") or 1)
MAX_DELAY = float(os.getenv("MAX_DELAY", "3") or 3)

# GraphQL doc IDs are configurable so they can be rotated without code changes.
PROFILE_DOC_ID = os.getenv("IG_PROFILE_DOC_ID", "25980296051578533")
POSTS_DOC_ID = os.getenv("IG_PROFILE_POSTS_DOC_ID", "24835958312750138")
SEARCH_DOC_ID = os.getenv("IG_SEARCH_DOC_ID", "24146980661639222")
IG_APP_ID = os.getenv("IG_APP_ID", "936619743392459")
ASBD_ID = os.getenv("IG_ASBD_ID", "359341")
BLOKS_VERSION_ID = os.getenv("IG_BLOKS_VERSION_ID", "41a4871badc8ef00114860033dd42edcd50935d511345a5a37fbaa878479ad3c")


class InstagramScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.instagram.com"
        self.graphql_url = "https://www.instagram.com/graphql/query"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
        }
        self.csrf_token = ''
        self.app_id = IG_APP_ID  # Instagram web app ID (override via env)
        self.search_doc_id = SEARCH_DOC_ID  # GraphQL doc ID for search
        self.lsd_token: str = os.getenv("IG_LSD_TOKEN", "")
        self._init_session()

    def _init_session(self):
        """Initialize session and get CSRF token"""
        try:
            response = self.session.get(self.base_url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            # Extract CSRF token from cookies
            self.csrf_token = response.cookies.get('csrftoken', '')
            # Also extract from HTML if needed
            if not self.csrf_token:
                m = re.search(r'"csrf_token":"([^"]+)"', response.text)
                if m:
                    self.csrf_token = m.group(1)
            # Try to capture LSD token from the bootstrap payload (used by IG GraphQL)
            if not self.lsd_token:
                lsd_match = re.search(r'"LSD",\[\],\{"token":"([^"]+)"\}', response.text)
                if lsd_match:
                    self.lsd_token = lsd_match.group(1)
            # Store session ID and other important cookies
            for cookie in response.cookies:
                self.session.cookies.set_cookie(cookie)
        except Exception:
            self.csrf_token = ''

    def _random_delay(self):
        """Add random delay to mimic human behavior"""
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    def _build_graphql_headers(self, friendly_name: Optional[str] = None, root_field: Optional[str] = None) -> Dict[str, str]:
        """Prepare headers for GraphQL calls."""
        headers = self.headers.copy()
        headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/',
            'X-IG-App-ID': self.app_id,
            'X-ASBD-ID': ASBD_ID,
            'X-Bloks-Version-Id': BLOKS_VERSION_ID,
        })
        if self.csrf_token:
            headers['X-CSRFToken'] = self.csrf_token
        if self.lsd_token:
            headers['X-FB-LSD'] = self.lsd_token
        if friendly_name:
            headers['X-FB-Friendly-Name'] = friendly_name
        if root_field:
            headers['X-IG-Root-Field-Name'] = root_field
        return headers

    def _post_graphql(self, doc_id: str, variables: Dict[str, Any], friendly_name: Optional[str] = None, root_field: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Execute a GraphQL POST with shared headers and variables."""
        try:
            payload = {
                'doc_id': doc_id,
                'variables': json.dumps(variables)
            }
            headers = self._build_graphql_headers(friendly_name=friendly_name, root_field=root_field)
            resp = self.session.post(self.graphql_url, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def _get_user_id(self, username: str) -> Optional[str]:
        """Resolve username to user id using Instagram's web profile info endpoint."""
        try:
            url = f"{self.base_url}/api/v1/users/web_profile_info/?username={username}"
            headers = self._build_graphql_headers()
            headers['Accept'] = 'application/json'
            resp = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return str(data.get('data', {}).get('user', {}).get('id') or '') or None
        except Exception:
            return None

    def _parse_graphql_profile(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract profile fields from GraphQL profile response."""
        user = self._extract_user_from_nested(data)
        if not user:
            return None
        return {
            'username': user.get('username'),
            'full_name': user.get('full_name'),
            'biography': user.get('biography', ''),
            'follower_count': user.get('follower_count') or user.get('edge_followed_by', {}).get('count', 0),
            'following_count': user.get('following_count') or user.get('edge_follow', {}).get('count', 0),
            'post_count': user.get('media_count') or user.get('edge_owner_to_timeline_media', {}).get('count', 0),
            'is_verified': user.get('is_verified', False),
            'is_private': user.get('is_private', False),
            'profile_pic_url': user.get('profile_pic_url_hd') or user.get('hd_profile_pic_url_info', {}).get('url') or user.get('profile_pic_url'),
            'external_url': user.get('external_url', ''),
            'category': user.get('category', ''),
        }

    def _fetch_profile_api(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch profile using Instagram's web profile info endpoint (no doc_id required)."""
        try:
            url = f"{self.base_url}/api/v1/users/web_profile_info/?username={username}"
            headers = self._build_graphql_headers()
            headers['Accept'] = 'application/json'
            headers['Referer'] = f"{self.base_url}/{username}/"
            resp = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None
            data = resp.json()
            user = data.get('data', {}).get('user', {})
            if not user:
                return None
            profile = {
                'username': user.get('username'),
                'full_name': user.get('full_name'),
                'biography': user.get('biography', ''),
                'follower_count': user.get('edge_followed_by', {}).get('count', user.get('follower_count', 0)),
                'following_count': user.get('edge_follow', {}).get('count', user.get('following_count', 0)),
                'post_count': user.get('edge_owner_to_timeline_media', {}).get('count', user.get('media_count', 0)),
                'is_verified': user.get('is_verified', False),
                'is_private': user.get('is_private', False),
                'profile_pic_url': user.get('profile_pic_url_hd') or user.get('hd_profile_pic_url_info', {}).get('url') or user.get('profile_pic_url'),
                'external_url': user.get('external_url', ''),
                'category': user.get('category', ''),
            }
            return {'profile': profile, 'user_id': str(user.get('id') or '')}
        except Exception:
            return None

    def _fetch_profile_graphql(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch profile using Instagram GraphQL (PolarisProfilePageContentQuery)."""
        user_id = self._get_user_id(username)
        if not user_id:
            return None

        variables = {
            "enable_integrity_filters": True,
            "id": user_id,
            "render_surface": "PROFILE"
        }

        result = self._post_graphql(
            doc_id=PROFILE_DOC_ID,
            variables=variables,
            friendly_name="PolarisProfilePageContentQuery",
            root_field="fetch__XDTUserDict"
        )
        if not result:
            return None

        profile = self._parse_graphql_profile(result.get('data', {}))
        if not profile:
            return None
        # Attach raw data to allow post extraction fallback
        return {
            'profile': profile,
            'raw': result.get('data', {})
        }

    def _fetch_posts_graphql(self, username: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch posts grid via GraphQL (PolarisProfilePostsQuery)."""
        variables = {
            "data": {
                "count": limit,
                "include_reel_media_seen_timestamp": True,
                "include_relationship_info": True,
                "latest_besties_reel_media": True,
                "latest_reel_media": True
            },
            "username": username,
            "__relay_internal__pv__PolarisIsLoggedInrelayprovider": True
        }

        result = self._post_graphql(
            doc_id=POSTS_DOC_ID,
            variables=variables,
            friendly_name="PolarisProfilePostsQuery",
            root_field="xdt_api__v1__feed__user_timeline_graphql_connection"
        )
        if not result:
            return []

        data = result.get('data', {})
        # Find the first connection that looks like the timeline
        connection = None
        for value in data.values():
            if isinstance(value, dict) and 'edges' in value:
                connection = value
                break
        if not connection:
            return []

        posts: List[Dict[str, Any]] = []
        edges = connection.get('edges', [])
        for edge in edges[:limit]:
            node = edge.get('node', {})
            posts.append({
                'shortcode': node.get('code') or node.get('shortcode'),
                'caption': self._get_caption(node),
                'like_count': node.get('like_count') or node.get('edge_liked_by', {}).get('count', 0),
                'comment_count': node.get('comment_count') or node.get('edge_media_to_comment', {}).get('count', 0),
                'timestamp': node.get('taken_at') or node.get('taken_at_timestamp'),
                'media_url': self._pick_media_url(node),
                'is_video': node.get('is_video', False)
            })
        return posts

    def _pick_media_url(self, node: Dict[str, Any]) -> Optional[str]:
        """Choose a display URL from node candidates."""
        if node.get('display_url'):
            return node.get('display_url')
        # Try image candidates
        candidates = node.get('image_versions2', {}).get('candidates', [])
        if candidates:
            return candidates[0].get('url')
        # Try video versions
        videos = node.get('video_versions', [])
        if videos:
            return videos[0].get('url')
        return None

    def search_users(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for Instagram users using GraphQL API"""
        try:
            self._random_delay()

            # Use Instagram's GraphQL API for search
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            headers['Origin'] = self.base_url
            headers['Referer'] = f'{self.base_url}/'
            
            if self.csrf_token:
                headers['X-CSRFToken'] = self.csrf_token
            headers['X-IG-App-ID'] = self.app_id
            headers['X-FB-Friendly-Name'] = 'PolarisSearchBoxRefetchableQuery'
            headers['X-Requested-With'] = 'XMLHttpRequest'

            # Build the GraphQL variables
            variables = {
                "data": {
                    "context": "blended",
                    "include_reel": "true",
                    "query": query,
                    "rank_token": "",
                    "search_session_id": f"{int(time.time() * 1000)}",
                    "search_surface": "web_top_search"
                },
                "hasQuery": True
            }

            # Prepare form data
            data = {
                'variables': json.dumps(variables),
                'doc_id': self.search_doc_id
            }

            response = self.session.post(
                self.graphql_url,
                headers=headers,
                data=data,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                result = response.json()
                users = []
                
                # Extract users from GraphQL response
                search_data = result.get('data', {}).get('xdt_api__v1__fbsearch__topsearch_connection', {})
                user_items = search_data.get('users', [])[:limit]

                for item in user_items:
                    user = item.get('user', {})
                    users.append({
                        'username': user.get('username'),
                        'full_name': user.get('full_name'),
                        'profile_pic': user.get('profile_pic_url'),
                        'is_verified': user.get('is_verified', False),
                        'follower_count': 0,  # Not included in search results
                        'is_private': False  # Not included in search results
                    })

                return users

            return []

        except Exception:
            return []

    def get_profile(self, username: str, include_posts: bool = False, post_limit: int = 12) -> Optional[Dict]:
        """Get Instagram profile data"""
        try:
            self._random_delay()

            posts: List[Dict[str, Any]] = []

            # Try web profile info API first (more stable than HTML)
            api_profile = self._fetch_profile_api(username)
            if api_profile:
                if include_posts:
                    posts = self._fetch_posts_graphql(username, post_limit)
                return {'profile': api_profile['profile'], 'posts': posts}

            # Preferred fallback: GraphQL profile fetch
            graphql_profile = self._fetch_profile_graphql(username)

            if include_posts and graphql_profile:
                posts = self._fetch_posts_graphql(username, post_limit)

            if graphql_profile:
                result: Dict[str, Any] = {
                    'profile': graphql_profile['profile'],
                    'posts': posts,
                }
                return result

            # Fallback: HTML parsing
            url = f"{self.base_url}/{username}/"
            headers = self.headers.copy()
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            
            response = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            if response.status_code == 404:
                return None

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            user_data = {}
            profile_data = None
            
            # Method 1: Extract from <script type="application/json"> tags (new Instagram structure)
            json_scripts = soup.find_all('script', type='application/json')
            for script in json_scripts:
                try:
                    if not script.string:
                        continue
                    data = json.loads(script.string)
                    # Look for user data in various paths
                    if isinstance(data, dict):
                        # Try to find user data in the nested structure
                        if 'require' in data:
                            # Complex nested structure
                            for item in data.get('require', []):
                                if isinstance(item, list):
                                    for subitem in item:
                                        if isinstance(subitem, dict):
                                            user_data = self._extract_user_from_nested(subitem)
                                            if user_data:
                                                break
                        elif 'data' in data:
                            user_data = self._extract_user_from_nested(data)
                        elif 'user' in data:
                            user_data = data['user']
                        
                        if user_data:
                            break
                except Exception:
                    continue
            
            # Method 2: Extract from JSON-LD structured data for basic info
            if not user_data:
                scripts = soup.find_all('script', type='application/ld+json')
                for script in scripts:
                    try:
                        data = json.loads(script.string or '{}')
                        if data.get('@type') == 'Person':
                            profile_data = data
                            # Build minimal user_data from JSON-LD
                            user_data = {
                                'username': data.get('alternateName', '').replace('@', ''),
                                'full_name': data.get('name', ''),
                                'biography': data.get('description', ''),
                                'profile_pic_url_hd': data.get('image', ''),
                                'external_url': data.get('url', ''),
                            }
                            break
                    except Exception:
                        continue

            if not user_data:
                return None

            # Build profile from available data
            profile = {
                'username': user_data.get('username', username),
                'full_name': user_data.get('full_name', user_data.get('fullName', '')),
                'biography': user_data.get('biography', user_data.get('bio', '')),
                'follower_count': user_data.get('edge_followed_by', {}).get('count') or user_data.get('followerCount', 0) or user_data.get('edge_followed_by.count', 0),
                'following_count': user_data.get('edge_follow', {}).get('count') or user_data.get('followingCount', 0) or user_data.get('edge_follow.count', 0),
                'post_count': user_data.get('edge_owner_to_timeline_media', {}).get('count') or user_data.get('mediaCount', 0),
                'is_verified': user_data.get('is_verified', user_data.get('isVerified', False)),
                'is_private': user_data.get('is_private', user_data.get('isPrivate', False)),
                'profile_pic_url': user_data.get('profile_pic_url_hd') or user_data.get('profilePicUrl', user_data.get('profile_pic_url', '')),
                'external_url': user_data.get('external_url', user_data.get('externalUrl', ''))
            }

            result: Dict[str, List[Dict] | Dict] = {'profile': profile}

            if include_posts and user_data:
                posts = self._extract_posts(user_data, post_limit)
                result['posts'] = posts

            return result

        except Exception:
            return None
    
    def _extract_user_from_nested(self, data: Dict) -> Optional[Dict]:
        """Recursively extract user data from nested dictionary"""
        if not isinstance(data, dict):
            return None
        
        # Check if this dict has user fields
        if 'username' in data and 'full_name' in data:
            return data
        if 'user' in data and isinstance(data['user'], dict):
            return data['user']
        
        # Recursively search
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

    def _extract_shared_data(self, html: str) -> Dict:
        """Extract shared data from HTML"""
        try:
            match = re.search(r'window\._sharedData\s*=\s*({.+?});', html)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
        return {}

    def _extract_posts(self, user_data: Dict, limit: int) -> List[Dict]:
        """Extract posts from user data"""
        posts: List[Dict] = []
        try:
            edges = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])

            for edge in edges[:limit]:
                node = edge.get('node', {})
                posts.append({
                    'shortcode': node.get('shortcode'),
                    'caption': self._get_caption(node),
                    'like_count': node.get('edge_liked_by', {}).get('count', 0),
                    'comment_count': node.get('edge_media_to_comment', {}).get('count', 0),
                    'timestamp': node.get('taken_at_timestamp'),
                    'media_url': node.get('display_url'),
                    'is_video': node.get('is_video', False)
                })
        except Exception:
            pass

        return posts

    def _get_caption(self, node: Dict) -> str:
        """Extract caption from post node"""
        try:
            if node.get('caption') and isinstance(node['caption'], dict):
                return node['caption'].get('text', '') or ''
            edges = node.get('edge_media_to_caption', {}).get('edges', [])
            if edges:
                return edges[0].get('node', {}).get('text', '')
        except Exception:
            pass
        return ''
