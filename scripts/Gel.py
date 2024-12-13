#The code is based on PyGelbooru https://pypi.org/project/pygelbooru/
import asyncio
import os
import reprlib
import xml
from datetime import datetime
from random import randint
from typing import *
from urllib.parse import urlparse

import aiohttp
import xmltodict
from furl import furl


class GelbooruException(Exception):
    pass


class GelbooruNotFoundException(GelbooruException):
    pass


class GelbooruImage:
    """
    Container for Gelbooru image results.
    Returns the image URL when cast to str
    """

    def __init__(self, payload: dict, gelbooru):
        self._gelbooru = gelbooru  # type: Gelbooru

        # Cross compatability with older Booru API's
        payload = {k.strip('@'): v for k, v in payload.items()}

        self.id             = int(payload.get('id', 0) or 0)                            # type: int
        self.creator_id     = int(payload.get('creator_id', 0) or 0) or None            # type: Optional[int]
        self.created_at     = _datetime(payload.get('created_at'))                      # type: Optional[datetime]
        self.file_url       = payload.get('file_url')                                   # type: str
        self.filename       = os.path.basename(urlparse(self.file_url).path)            # type: str
        self.source         = payload.get('source') or None                             # type: Optional[str]
        self.hash           = payload.get('md5')                                        # type: str
        self.height         = int(payload.get('height'))                                # type: int
        self.width          = int(payload.get('width'))                                 # type: int
        self.rating         = payload.get('rating')                                     # type: str
        self.has_sample     = payload.get('has_sample', 'false').lower() == 'true'      # type: bool
        self.has_comments   = payload.get('has_comments', 'false').lower() == 'true'    # type: bool
        self.has_notes      = payload.get('has_notes', 'false').lower() == 'true'       # type: bool
        self.has_children   = payload.get('has_children', 'false').lower() == 'true'    # type: bool
        self.tags           = str(payload.get('tags')).split(' ')                       # type: List[str]
        self.change         = datetime.fromtimestamp(int(payload.get('change', 0)))     # type: datetime
        self.directory      = payload.get('directory')                                  # type: str
        self.status         = payload.get('status')                                     # type: str
        self.locked         = bool(int(payload.get('post_locked', 0) or 0))             # type: bool
        self.score          = int(payload.get('score', 0) or 0)                         # type: int
        self._payload       = payload                                                   # type: dict

    def __str__(self):
        return f"https://gelbooru.com/index.php?page=post&s=view&id={self.id}"

    def __int__(self):
        return self.id

    def __repr__(self):
        rep = reprlib.Repr()
        return f"<GelbooruImage(id={self.id}, filename={rep.repr(self.filename)}, owner={rep.repr(self.creator_id)})>"
    
    def get_tags(self):
        return self.tags


API_GELBOORU = 'https://gelbooru.com/'

class Gelbooru:
    SORT_COUNT = 'count'
    SORT_DATE = 'date'
    SORT_NAME = 'name'

    SORT_ASC = 'ASC'
    SORT_DESC = 'DESC'

    def __init__(self, api_key: Optional[str] = None,
                 user_id: Optional[str] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None,
                 api: Optional[str] = API_GELBOORU):
        """
        API credentials can be obtained here (registration required):
        https://gelbooru.com/index.php?page=account&s=options
        Args:
            api_key (str): API Key
            user_id (str): User ID
            loop (asyncio.AbstractEventLoop): Event loop to use
            api (str): Gelbooru compatible API endpoint to use
        """
        self._api_key = api_key
        self._user_id = user_id
        self._loop = loop
        self._base_url = api

    async def get_post(self, post_id: int) -> Optional[GelbooruImage]:
        """
        Get a specific Gelbooru post by its ID
        Args:
            post_id (int): The post id to lookup
        Raises:
            GelbooruNotFoundException: Raised if Gelbooru returns an empty result for this query
        """
        endpoint = self._endpoint('post')
        endpoint.args['id'] = post_id

        # Fetch and parse XML, then make sure we actually have results
        payload = await self._request(str(endpoint))
        payload = xmltodict.parse(payload)

        # Cross compatability with older Booru API's
        payload = {k.strip('@'): v for k, v in payload.items()}

        if 'posts' not in payload:
            raise GelbooruNotFoundException(f"Could not find a post with the ID {post_id}")

        return GelbooruImage(payload['posts']['post'], self)

    async def random_post(self, *, tags: Optional[List[str]] = None,
                          exclude_tags: Optional[List[str]] = None) -> Optional[List[GelbooruImage]]:
        """
        Search for and return a single random image with the specified tags.
        Args:
            tags (list of str): A list of tags to search for
            exclude_tags (list of str): A list of tags to EXCLUDE from search results
        Returns:
            GelbooruImage or None: Returns None if no posts are found with the specified tags.
        """
        endpoint = self._endpoint('post')
        endpoint.args['limit'] = 1

        # Apply basic tag formatting
        tags = self._format_tags(tags, exclude_tags)
        if tags:
            endpoint.args['tags'] = ' '.join(tags)

        # Run the initial query to get the number of posts available
        payload = await self._request(str(endpoint))
        try:
            payload = xmltodict.parse(payload)

            # Cross compatability with older Booru API's
            payload = {k.strip('@'): v for k, v in payload.items()}
        except xml.parsers.expat.ExpatError:
            raise GelbooruException("Gelbooru returned a malformed response")

        # Count is 0? We have no results to fetch then
        count = int(payload['posts']['@count'])
        if not count:
            return None

        # Otherwise, let's pull a random ID from the number of posts
        offset = randint(0, min(count, 20000))

        return await self.search_posts(tags=tags, exclude_tags=exclude_tags, limit=1, page=offset)

    async def search_posts(self, *, tags: Optional[List[str]] = None,
                           exclude_tags: Optional[List[str]] = None,
                           limit: int = 100,
                           page: int = 0) -> Union[List[GelbooruImage], GelbooruImage]:
        """
        Search for images with the optionally specified tag(s)
        Args:
            tags (list of str): A list of tags to search for
            exclude_tags (list of str): A list of tags to EXCLUDE from search results
            limit (int): Limit the number of results returned. Defaults to 100
            page (int): The page number
        Returns:
            list of GelbooruImage or GelbooruImage: Returns a single GelbooruImage of a limit of 1 is supplied
        """
        endpoint = self._endpoint('post')
        endpoint.args['limit'] = limit
        endpoint.args['pid'] = page

        # Apply basic tag formatting
        tags = self._format_tags(tags, exclude_tags)
        if tags:
            endpoint.args['tags'] = ' '.join(tags)

        # Fetch and parse XML, then make sure we actually have results
        payload = await self._request(str(endpoint))
        try:
            payload = xmltodict.parse(payload)
        except xml.parsers.expat.ExpatError:
            raise GelbooruException("Gelbooru returned a malformed response")
        if 'posts' not in payload or 'post' not in payload["posts"]:
            return []

        # Single results are not returned as arrays/lists and need to be processed directly instead of iterated
        result = [GelbooruImage(p, self) for p in payload['posts']['post']] \
            if isinstance(payload['posts']['post'], list) \
            else [GelbooruImage(payload['posts']['post'], self)]

        # Return the first result if we have a limit of 1 explicitly set
        if limit == 1:
            return result[0]
        else:
            return result

    def _endpoint(self, s: str) -> furl:
        endpoint = furl(self._base_url)
        endpoint.args['page'] = 'dapi'
        endpoint.args['s'] = s
        endpoint.args['q'] = 'index'
        # endpoint.args['json'] = '1'

        # Append API key if available
        if self._api_key:
            endpoint.args['api_key'] = self._api_key
        if self._user_id:
            endpoint.args['user_id'] = self._user_id

        return endpoint

    def _format_tags(self, tags: list, exclude_tags: list):
        """
        Apply basic tag formatting
        Args:
            tags (list of str): A list of tags to search for
            exclude_tags (list of str): A list of tags to EXCLUDE from search results
        Returns:
            list of str
        """
        # Apply basic tag formatting
        tags = [tag.strip().lower().replace(' ', '_') for tag in tags] if tags else []
        exclude_tags = ['-' + tag.strip().lstrip('-').lower().replace(' ', '_') for tag in
                        exclude_tags] if exclude_tags else []

        return tags + exclude_tags

    async def _request(self, url: str) -> bytes:
        async with aiohttp.ClientSession(loop=self._loop) as session:
            status_code, response = await self._fetch(session, url)

        if status_code not in [200, 201]:
            raise GelbooruException(f"""Gelbooru returned a non 200 status code: {response}""")

        return response

    async def _fetch(self, session: aiohttp.ClientSession, url) -> Tuple[int, bytes]:
        async with session.get(url) as response:
            return response.status, await response.read()


def _datetime(date: str, format='%a %b %d %H:%M:%S %z %Y') -> Optional[datetime]:
    """
    Convert a date string to a datetime object
    Args:
        date (str): The date string to convert
        format (str): The format of the date string
    Returns:
        datetime
    """
    try:
        return datetime.strptime(date, format)
    except ValueError:
        return None
