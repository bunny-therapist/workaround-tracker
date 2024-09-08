from __future__ import annotations

import atexit
import functools
import logging
import urllib.parse
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:  # pragma: no cover
    import sys

    if sys.version_info >= (3, 11):
        pass
    else:
        pass

from ._base import IssueChecker

LOGGER = logging.getLogger(__name__)

GITHUB_MEDIA_TYPE = "application/vnd.github+json"


class GithubIssueChecker(IssueChecker):
    def __init__(self, url: str, token: str) -> None:
        split_result = urllib.parse.urlsplit(url)
        self._scheme = split_result.scheme
        self._netloc = split_result.netloc
        self._token = token

    @functools.cached_property
    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers = {
            "Accept": GITHUB_MEDIA_TYPE,
            "Bearer": self._token,
        }
        atexit.register(session.close)
        return session

    def is_issue_resolved(self, url: str) -> bool | None:
        LOGGER.debug(
            "Checking if the url %s is a Github URL that this IssueChecker can handle",
            url,
        )
        split_result = urllib.parse.urlsplit(url)

        if split_result.netloc != self._netloc:
            LOGGER.debug("... it is not (%s != %s)", split_result.netloc, self._netloc)
            return None

        LOGGER.debug("URL %s has a matching netloc - will query github", url)
        response = self._session.get(
            url=urllib.parse.urlunsplit(
                (
                    self._scheme,
                    f"api.{split_result.netloc}",
                    f"/repos{split_result.path}",
                    None,
                    None,
                )
            ),
        )
        response.raise_for_status()
        is_closed: bool = response.json()["state"] == "closed"
        return is_closed
