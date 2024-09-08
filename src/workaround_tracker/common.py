import sys
from pathlib import Path
from typing import Any, Literal

import pydantic
import yaml

if sys.version_info >= (3, 11):  # pragma: no cover
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self

WORKAROUND_COMMENT_PREFIX = "WORKAROUND"
CACHE_FILE_NAME = ".workaround-tracker-cache.json"


class WorkaroundTrackerError(Exception):
    """Base class for errors in workaround-tracker."""


class Workaround(pydantic.BaseModel):
    """A workaround in the code.

    Attributes:
        file: The path to the file.
        line: The line number.
        url: The url to the issue the workaround is for.

    """

    file: Path
    line: int
    url: str


class AuthenticationConfig(pydantic.BaseModel):
    """Configuration for authentication to an issue tracker."""

    env: str


class IssueTrackerConfig(pydantic.BaseModel):
    """Configuration for a single issue tracker, e.g., a github instance."""

    kind: Literal["github"]
    host: str = pydantic.Field(pattern=r"[^/]+")
    authentication: AuthenticationConfig

    @pydantic.model_validator(mode="before")
    @classmethod
    def default_host(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("kind") == "github":
            data.setdefault("host", "github.com")
        return data  # pragma: no cover


class Config(pydantic.BaseModel):
    """The main configuration of workaround-tracker."""

    scanners: list[Literal["python"]] = pydantic.Field(default=["python"])
    issue_trackers: list[IssueTrackerConfig] = pydantic.Field(default_factory=list)

    @classmethod
    def _from_dict(cls: type[Self], d: dict[str, Any]) -> Self:
        return cls.model_validate(d)

    @classmethod
    def from_yaml_file(cls: type[Self], config_file: Path) -> Self:
        with config_file.open() as config_filehandle:
            config_content = yaml.safe_load(config_filehandle)
        return cls._from_dict(config_content)
