import logging
from pathlib import Path
from typing import Optional

import click

from workaround_tracker.code_scanner import CodeScannerCache, CodeScannerManager
from workaround_tracker.common import CACHE_FILE_NAME, Config
from workaround_tracker.issue_checker import IssueCheckerManager

LOGGER = logging.getLogger(__name__)
EXIT_CODE_REDUNDANT_WORKAROUNDS = 3


def setup_logging(*, debug: bool = False) -> None:
    root_logger = logging.getLogger()
    root_logger.addHandler(logging.StreamHandler())
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)


def read_cache_file(cache_file: Path) -> CodeScannerCache:
    if cache_file.exists():
        return CodeScannerCache.from_json_file(cache_file)
    return CodeScannerCache()


@click.command()
@click.argument(
    "source_paths",
    type=click.Path(exists=True, readable=True, path_type=Path),
    nargs=-1,
)
@click.option(
    "--config-file",
    type=click.Path(readable=True, exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--cache-file",
    type=click.Path(readable=True, writable=True, path_type=Path),
    default=Path.cwd() / CACHE_FILE_NAME,
)
@click.option("--cache/--no-cache", default=True)
@click.option("--debug", is_flag=True)
def check(
    source_paths: list[Path],
    *,
    config_file: Path,
    cache_file: Path,
    cache: bool,
    debug: bool,
) -> None:
    setup_logging(debug=debug)

    if not source_paths:
        LOGGER.debug("No source paths - done")
        raise SystemExit(0)

    code_scanner_cache: Optional[CodeScannerCache] = None
    if cache:
        code_scanner_cache = read_cache_file(cache_file)
    config = Config.from_yaml_file(config_file)
    code_scanner_manager = CodeScannerManager.from_scanner_strings(
        strings=config.scanners,
        cache=code_scanner_cache,
    )
    issue_checker_manager = IssueCheckerManager.from_config(config.issue_trackers)

    found_redundant_workarounds = False
    for source_path in source_paths:
        for workaround in code_scanner_manager.scan_path(source_path):
            LOGGER.debug(
                "Found workaround in %s at L%s", workaround.file, workaround.line
            )
            if issue_checker_manager.is_workaround_redundant(workaround):
                LOGGER.info(
                    "%s L%s RESOLVED: %s",
                    workaround.file,
                    workaround.line,
                    workaround.url,
                )
                found_redundant_workarounds = True

    if code_scanner_cache:
        LOGGER.debug("Writing cache to %s", cache_file)
        code_scanner_manager.cache.write_to_json_file(cache_file)

    raise SystemExit(
        EXIT_CODE_REDUNDANT_WORKAROUNDS if found_redundant_workarounds else 0
    )
