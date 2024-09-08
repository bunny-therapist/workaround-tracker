from __future__ import annotations

import functools
import logging
import os
from typing import TYPE_CHECKING, Iterable

import cachetools
from cachetools.keys import hashkey

if TYPE_CHECKING:  # pragma: no cover
    import sys

    from ._base import IssueChecker

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self

from workaround_tracker.common import (
    IssueTrackerConfig,
    Workaround,
    WorkaroundTrackerError,
)

from ._github import GithubIssueChecker

LOGGER = logging.getLogger(__name__)


class UnknownIssueResolutionError(WorkaroundTrackerError):
    """Known when there is no way to determine if an issue is resolved."""


def _workaround_url_hash_key(
    _: IssueCheckerManager, workaround: Workaround, method: str
) -> tuple:  # type: ignore[type-arg]
    return hashkey(workaround.url, method)


class IssueCheckerManager:
    def __init__(self, issue_checkers: Iterable[IssueChecker]) -> None:
        self._issue_checkers = list(issue_checkers)
        self._runtime_cache = cachetools.LRUCache(maxsize=64)  # type: ignore[var-annotated]

    @classmethod
    def from_config(cls: type[Self], configs: Iterable[IssueTrackerConfig]) -> Self:
        issue_checkers: list[IssueChecker] = []
        for config in configs:
            if config.kind == "github":
                issue_checkers.append(
                    GithubIssueChecker(
                        url=f"https://{config.host}",
                        token=os.environ[config.authentication.env],
                    )
                )
            else:  # pragma: no cover
                # Should be prevented by configuration validation
                raise AssertionError("Unknown issue tracker kind: %s", config.kind)
        return cls(issue_checkers=issue_checkers)

    @cachetools.cachedmethod(
        lambda self: self._runtime_cache,
        key=functools.partial(
            _workaround_url_hash_key, method="is_workaround_redundant"
        ),
    )
    def is_workaround_redundant(self, workaround: Workaround) -> bool:
        LOGGER.debug(
            "Checking if the workaround in %s at L%s is resolved",
            workaround.file,
            workaround.line,
        )
        for issue_checker in self._issue_checkers:
            is_resolved: bool | None = issue_checker.is_issue_resolved(workaround.url)
            if is_resolved is not None:
                LOGGER.debug("%s resolved: %s", workaround.url, is_resolved)
                return is_resolved
            LOGGER.debug("%s cannot determine if the issue is resolved", issue_checker)
        raise UnknownIssueResolutionError("Could not determine if issue is resolved")
