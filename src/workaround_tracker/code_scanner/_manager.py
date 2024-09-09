from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Literal

import pydantic

if TYPE_CHECKING:  # pragma: no cover
    import sys
    from collections.abc import Container, Generator, Iterable, Mapping
    from pathlib import Path

    from ._base import CodeScanner

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self

from workaround_tracker.common import ConsistentPath, Workaround, WorkaroundTrackerError

from ._python import PythonCodeScanner

LOGGER = logging.getLogger(__name__)


class NoCodeScannersError(WorkaroundTrackerError):
    """Raised when there are no code scanners so code cannot be scanned."""


class OverlappingCodeScannersError(WorkaroundTrackerError):
    """Raised when code scanners have overlapping file suffixes."""


class FileScanCache(pydantic.BaseModel):
    workarounds: list[Workaround]
    timestamp: float


class CodeScannerCache(pydantic.BaseModel):
    files: dict[ConsistentPath, FileScanCache] = pydantic.Field(default_factory=dict)

    @classmethod
    def _from_dict(cls: type[Self], d: dict[str, Any]) -> Self:
        return cls.model_validate(d)

    @classmethod
    def from_json_file(cls: type[Self], cache_file: Path) -> Self:
        with cache_file.open() as cache_filehandle:
            cache_content = json.load(cache_filehandle)
        return cls._from_dict(cache_content)

    def write_to_json_file(self, cache_file: Path) -> None:
        with cache_file.open(mode="w") as cache_filehandle:
            json.dump(self.model_dump(mode="json"), cache_filehandle)


class CodeScannerManager:
    def __init__(
        self,
        code_scanners: Iterable[CodeScanner],
        cache: CodeScannerCache | None = None,
    ) -> None:
        if not code_scanners:
            raise NoCodeScannersError("No code scanners provided")
        self._code_scanners = list(code_scanners)
        self._cache = cache or CodeScannerCache()
        self._suffix_to_code_scanner_map: Mapping[str, CodeScanner] = {}
        for code_scanner in self._code_scanners:
            for file_suffix in code_scanner.get_file_suffixes():
                if file_suffix in self._suffix_to_code_scanner_map:
                    raise OverlappingCodeScannersError(
                        f"{file_suffix} in multiple code scanners"
                    )
                self._suffix_to_code_scanner_map[file_suffix] = code_scanner

    @property
    def cache(self) -> CodeScannerCache:
        return self._cache

    @classmethod
    def from_scanner_strings(
        cls,
        strings: Container[Literal["python"]],
        cache: CodeScannerCache | None = None,
    ) -> Self:
        code_scanners: list[CodeScanner] = []
        if "python" in strings:
            code_scanners.append(PythonCodeScanner())
        return cls(
            code_scanners=code_scanners,
            cache=cache,
        )

    def _scan_file_using_code_scanners(
        self, path: Path
    ) -> Generator[Workaround, None, None]:
        LOGGER.debug("Scanning %s", path)
        found_workarounds: list[Workaround] = []
        with path.open() as file_to_scan:
            code_scanner = self._suffix_to_code_scanner_map[path.suffix]
            LOGGER.debug("Using %s on %s", code_scanner, path)
            for line_number, url in code_scanner.scan_file(file_to_scan):
                LOGGER.debug(
                    "%s found a workaround on line %s", code_scanner, line_number
                )
                workaround = Workaround(
                    file=path,
                    line=line_number,
                    url=url,
                )
                yield workaround
                found_workarounds.append(workaround)
        self._cache.files[path] = FileScanCache(
            workarounds=found_workarounds,
            timestamp=time.time(),
        )

    def _scan_file(self, path: Path) -> Generator[Workaround, None, None]:
        LOGGER.debug("Processing %s", path)
        file_scan_cache: FileScanCache | None = self._cache.files.get(path)
        if file_scan_cache is not None:
            last_modified_time: float = path.stat().st_mtime
            last_checked_time: float = file_scan_cache.timestamp
            if last_checked_time < last_modified_time:
                yield from self._scan_file_using_code_scanners(path)
            else:
                yield from file_scan_cache.workarounds
        else:
            yield from self._scan_file_using_code_scanners(path)

    def scan_path(self, path: Path) -> Generator[Workaround, None, None]:
        LOGGER.debug("Globing %s recursively", path)
        for file in path.rglob("**/*"):
            LOGGER.debug("Examining %s", file)
            if not file.is_file():
                LOGGER.debug("Not a file - skipping")
                continue
            LOGGER.debug("%s is a file", file)
            if file.suffix in self._suffix_to_code_scanner_map:
                LOGGER.debug("File suffix %s matches - scan file", file.suffix)
                yield from self._scan_file(file)
        LOGGER.debug("Done scanning %s", path)
