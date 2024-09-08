import itertools
from pathlib import Path
from unittest.mock import Mock, call

import pytest
from click.testing import CliRunner
from requests_mock import Mocker as RequestsMock

from workaround_tracker.code_scanner import CodeScannerCache, CodeScannerManager
from workaround_tracker.common import CACHE_FILE_NAME, Config, Workaround
from workaround_tracker.issue_checker import IssueCheckerManager
from workaround_tracker.issue_checker._github import GITHUB_MEDIA_TYPE
from workaround_tracker.main import (
    EXIT_CODE_REDUNDANT_WORKAROUNDS,
    check,
    read_cache_file,
    setup_logging,
)


@pytest.fixture
def mock_code_scanner_cache(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr(
        "workaround_tracker.main.CodeScannerCache",
        mock_object := Mock(spec=CodeScannerCache),
    )
    return mock_object


def test_read_cache_file__exists(tmp_path: Path, mock_code_scanner_cache: Mock) -> None:
    cache_file = tmp_path / "cache.yml"
    cache_file.touch()
    actual = read_cache_file(cache_file)
    mock_code_scanner_cache.from_json_file.assert_called_once_with(cache_file)
    assert actual is mock_code_scanner_cache.from_json_file.return_value


def test_read_cache_file__does_not_exists(
    tmp_path: Path, mock_code_scanner_cache: Mock
) -> None:
    cache_file = tmp_path / "cache.yml"
    actual = read_cache_file(cache_file)
    mock_code_scanner_cache.assert_called_once_with()
    mock_code_scanner_cache.from_json_file.assert_not_called()
    assert actual is mock_code_scanner_cache.return_value


@pytest.fixture
def mock_read_cache_file(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr(
        "workaround_tracker.main.read_cache_file",
        mock_object := Mock(spec=read_cache_file),
    )
    return mock_object


@pytest.fixture
def mock_config(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr(
        "workaround_tracker.main.Config", mock_object := Mock(spec=Config)
    )
    return mock_object


WORKAROUND_RESOLVED = Workaround(
    file=Path("file"), line=12, url="https://issue.tracker/issue/11"
)
WORKAROUND_UNRESOLVED = Workaround(
    file=Path("other_file"), line=36, url="https://issue.tracker/issue/14"
)


@pytest.fixture
def mock_code_scanner_manager(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr(
        "workaround_tracker.main.CodeScannerManager",
        mock_object := Mock(spec=CodeScannerManager),
    )
    mock_object.from_scanner_strings.return_value.scan_path.side_effect = [
        [],
        [WORKAROUND_RESOLVED, WORKAROUND_UNRESOLVED],
    ]
    return mock_object


@pytest.fixture
def mock_issue_checker_manager(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr(
        "workaround_tracker.main.IssueCheckerManager",
        mock_object := Mock(spec=IssueCheckerManager),
    )
    mock_object.from_config.return_value.is_workaround_redundant.side_effect = [
        True,
        False,
    ]
    return mock_object


def test_check__help() -> None:
    result = CliRunner().invoke(check, ["--help"])
    assert result.exit_code == 0
    assert result.stdout


@pytest.fixture
def existing_config_file(tmp_path: Path) -> Path:
    cache_file = tmp_path / "cache.yml"
    cache_file.touch()
    return cache_file


@pytest.fixture
def mock_setup_logging(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr(
        "workaround_tracker.main.setup_logging",
        mock_object := Mock(spec=setup_logging),
    )
    return mock_object


@pytest.mark.parametrize("debug", [True, False])
def test_check__no_source_paths(
    existing_config_file: Path,
    mock_setup_logging: Mock,
    mock_read_cache_file: Mock,
    mock_config: Mock,
    mock_code_scanner_manager: Mock,
    mock_issue_checker_manager: Mock,
    tmp_path: Path,
    debug: bool,
) -> None:
    command = ["--config-file", str(existing_config_file)]
    if debug:
        command.append("--debug")
    result = CliRunner().invoke(check, command)

    mock_setup_logging.assert_called_once_with(debug=debug)
    mock_read_cache_file.assert_not_called()
    mock_config.assert_not_called()
    mock_code_scanner_manager.assert_not_called()
    mock_issue_checker_manager.assert_not_called()
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "use_cache, provide_cache_file", itertools.product([True, False], [True, False])
)
def test_check(
    tmp_path_factory: pytest.TempPathFactory,
    existing_config_file: Path,
    mock_setup_logging: Mock,
    mock_read_cache_file: Mock,
    mock_config: Mock,
    mock_code_scanner_manager: Mock,
    mock_issue_checker_manager: Mock,
    tmp_path: Path,
    use_cache: bool,
    provide_cache_file: bool,
) -> None:
    source_paths = [tmp_path_factory.mktemp("src0"), tmp_path_factory.mktemp("src1")]
    command: list[str] = [str(source_path) for source_path in source_paths]

    command.append("--config-file")
    command.append(str(existing_config_file))

    cache_file = Path.cwd() / CACHE_FILE_NAME
    if provide_cache_file:
        cache_file = tmp_path_factory.mktemp("cache.json")
        command.append("--cache-file")
        command.append(str(cache_file))
    cache_file.touch()

    if not use_cache:
        command.append("--no-cache")

    result = CliRunner().invoke(check, command)

    mock_setup_logging.assert_called_once_with(debug=False)
    if use_cache:
        mock_read_cache_file.assert_called_once_with(cache_file)
        mock_code_scanner_manager.from_scanner_strings.assert_called_once_with(
            strings=mock_config.from_yaml_file.return_value.scanners,
            cache=mock_read_cache_file.return_value,
        )
    else:
        mock_read_cache_file.assert_not_called()
        mock_code_scanner_manager.from_scanner_strings.assert_called_once_with(
            strings=mock_config.from_yaml_file.return_value.scanners, cache=None
        )
    mock_config.from_yaml_file.assert_called_once_with(existing_config_file)
    mock_issue_checker_manager.from_config.assert_called_once_with(
        mock_config.from_yaml_file.return_value.issue_trackers
    )
    assert (
        mock_code_scanner_manager.from_scanner_strings.return_value.scan_path.mock_calls
        == [call(source_path) for source_path in source_paths]
    )
    assert (
        mock_issue_checker_manager.from_config.return_value.is_workaround_redundant.mock_calls
        == [call(WORKAROUND_RESOLVED), call(WORKAROUND_UNRESOLVED)]
    )
    if use_cache:
        mock_code_scanner_manager.from_scanner_strings.return_value.cache.write_to_json_file.assert_called_once_with(
            cache_file
        )
    else:
        mock_code_scanner_manager.from_scanner_strings.return_value.cache.write_to_json_file.assert_not_called()
    assert result.exit_code == EXIT_CODE_REDUNDANT_WORKAROUNDS


@pytest.mark.integration_test
def test_check__integration(
    requests_mock: RequestsMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    github_token = "gh_my_token"
    monkeypatch.setenv("GITHUB_TOKEN", github_token)
    monkeypatch.setenv("LOCAL_GITHUB_TOKEN", github_token)
    request_headers = {
        "Accept": GITHUB_MEDIA_TYPE,
        "Bearer": github_token,
    }
    requests_mock.get(
        "https://api.github.com/repos/litestar-org/litestar/issues/3630",
        json={"state": "closed"},
        request_headers=request_headers,
        headers={"Content-Type": GITHUB_MEDIA_TYPE},
    )
    requests_mock.get(
        "https://api.github.com/repos/mam-dev/security-constraints/issues/32",
        json={"state": "open"},
        request_headers=request_headers,
        headers={"Content-Type": GITHUB_MEDIA_TYPE},
    )
    config_file = Path(__file__).parent / "data" / "config" / "config_0.yaml"
    source_path = Path(__file__).parent / "data" / "code"

    result = CliRunner().invoke(
        check,
        [str(source_path), "--no-cache", "--config-file", str(config_file), "--debug"],
    )
    assert result.exit_code == EXIT_CODE_REDUNDANT_WORKAROUNDS
    assert (
        "RESOLVED: https://github.com/litestar-org/litestar/issues/3630"
        in result.stdout
    )
