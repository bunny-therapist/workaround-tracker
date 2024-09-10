from pathlib import Path
from unittest.mock import Mock

import pytest
from requests import HTTPError
from requests_mock import Mocker as RequestsMock

from workaround_tracker.common import (
    AuthenticationConfig,
    IssueTrackerConfig,
    Workaround,
)
from workaround_tracker.issue_checker import IssueCheckerManager
from workaround_tracker.issue_checker._base import IssueChecker
from workaround_tracker.issue_checker._github import (
    GITHUB_MEDIA_TYPE,
    GithubIssueChecker,
)
from workaround_tracker.issue_checker._gitlab import GitlabIssueChecker
from workaround_tracker.issue_checker._manager import UnknownIssueResolutionError

GITHUB_HOSTNAME = "mock.github"
GITHUB_URL = f"https://{GITHUB_HOSTNAME}"
GITHUB_TOKEN = "gh_token"
GITHUB_ISSUE_URL = "https://mock.github/org/proj/issues/1234"
GITHUB_API_ISSUE_URL = "https://api.mock.github/repos/org/proj/issues/1234"
GITHUB_AUTHENTICATION_ENV_VAR = "GITHUB_AUTH_TOKEN"
ISSUE_TRACKER_CONFIG_GITHUB = IssueTrackerConfig(
    kind="github",
    host=GITHUB_HOSTNAME,
    authentication=AuthenticationConfig(env=GITHUB_AUTHENTICATION_ENV_VAR),
)
WORKAROUND = Workaround(file=Path("file"), line=47, url=GITHUB_ISSUE_URL)
GITHUB_REQUEST_HEADERS = {
    "Accept": GITHUB_MEDIA_TYPE,
    "Bearer": GITHUB_TOKEN,
}

GITLAB_HOSTNAME = "mock.gitlab"
GITLAB_URL = f"https://{GITLAB_HOSTNAME}"
GITLAB_ISSUE_URL = f"https://{GITLAB_HOSTNAME}/group/proj/issues/64"
GITLAB_API_ISSUE_URL = (
    f"https://{GITLAB_HOSTNAME}/api/v4/projects/group%2Fproj/issues/64"
)
GITLAB_TOKEN = "gl_token"
GITLAB_AUTHENTICATION_ENV_VAR = "GITLAB_AUTH_TOKEN"
ISSUE_TRACKER_CONFIG_GITLAB = IssueTrackerConfig(
    kind="gitlab",
    host=GITLAB_HOSTNAME,
    authentication=AuthenticationConfig(env=GITLAB_AUTHENTICATION_ENV_VAR),
)
GITLAB_REQUEST_HEADERS = {
    "PRIVATE-TOKEN": GITLAB_TOKEN,
}


@pytest.fixture
def github_issue_checker() -> GithubIssueChecker:
    return GithubIssueChecker(
        url=GITHUB_URL,
        token=GITHUB_TOKEN,
    )


def test_github_issue_checker__is_issue_resolved__true(
    github_issue_checker: GithubIssueChecker, requests_mock: RequestsMock
) -> None:
    requests_mock.get(
        GITHUB_API_ISSUE_URL,
        json={"state": "closed"},
        request_headers=GITHUB_REQUEST_HEADERS,
    )
    is_resolved = github_issue_checker.is_issue_resolved(GITHUB_ISSUE_URL)
    assert is_resolved is True


def test_github_issue_checker__is_issue_resolved__false(
    github_issue_checker: GithubIssueChecker, requests_mock: RequestsMock
) -> None:
    requests_mock.get(
        GITHUB_API_ISSUE_URL,
        json={"state": "open"},
        request_headers=GITHUB_REQUEST_HEADERS,
    )
    is_resolved = github_issue_checker.is_issue_resolved(GITHUB_ISSUE_URL)
    assert is_resolved is False


def test_github_issue_checker__is_issue_resolved__no_match(
    github_issue_checker: GithubIssueChecker,
) -> None:
    is_resolved = github_issue_checker.is_issue_resolved(
        "https://some.github/org/proj/issues/1234"
    )
    assert is_resolved is None


def test_github_issue_checker__is_issue_resolved__error(
    github_issue_checker: GithubIssueChecker, requests_mock: RequestsMock
) -> None:
    requests_mock.get(
        GITHUB_API_ISSUE_URL,
        status_code=500,
        request_headers=GITHUB_REQUEST_HEADERS,
    )
    with pytest.raises(HTTPError):
        _ = github_issue_checker.is_issue_resolved(GITHUB_ISSUE_URL)


@pytest.fixture
def gitlab_issue_checker() -> GitlabIssueChecker:
    return GitlabIssueChecker(
        url=GITLAB_URL,
        token=GITLAB_TOKEN,
    )


def test_gitlab_issue_checker__is_issue_resolved__true(
    gitlab_issue_checker: GitlabIssueChecker, requests_mock: RequestsMock
) -> None:
    requests_mock.get(
        GITLAB_API_ISSUE_URL,
        json={"state": "closed"},
        request_headers=GITLAB_REQUEST_HEADERS,
    )
    is_resolved = gitlab_issue_checker.is_issue_resolved(GITLAB_ISSUE_URL)
    assert is_resolved is True


def test_gitlab_issue_checker__is_issue_resolved__false(
    gitlab_issue_checker: GitlabIssueChecker, requests_mock: RequestsMock
) -> None:
    requests_mock.get(
        GITLAB_API_ISSUE_URL,
        json={"state": "open"},
        request_headers=GITLAB_REQUEST_HEADERS,
    )
    is_resolved = gitlab_issue_checker.is_issue_resolved(GITLAB_ISSUE_URL)
    assert is_resolved is False


def test_gitlab_issue_checker__is_issue_resolved__no_match(
    gitlab_issue_checker: GitlabIssueChecker,
) -> None:
    is_resolved = gitlab_issue_checker.is_issue_resolved(
        "https://some.gitlab/someone/something/issues/1234"
    )
    assert is_resolved is None


def test_gitlab_issue_checker__is_issue_resolved__error(
    gitlab_issue_checker: GitlabIssueChecker, requests_mock: RequestsMock
) -> None:
    requests_mock.get(
        GITLAB_API_ISSUE_URL,
        status_code=500,
        request_headers=GITLAB_REQUEST_HEADERS,
    )
    with pytest.raises(HTTPError):
        _ = gitlab_issue_checker.is_issue_resolved(GITLAB_ISSUE_URL)


@pytest.fixture
def mock_issue_checker__true() -> Mock:
    return Mock(spec=IssueChecker, is_issue_resolved=Mock(return_value=True))


@pytest.fixture
def mock_issue_checker__none() -> Mock:
    return Mock(spec=IssueChecker, is_issue_resolved=Mock(return_value=None))


@pytest.fixture
def issue_checker_manager(
    mock_issue_checker__none: IssueChecker, mock_issue_checker__true: IssueChecker
) -> IssueCheckerManager:
    return IssueCheckerManager(
        issue_checkers=[mock_issue_checker__none, mock_issue_checker__true]
    )


def test_issue_checker_manager__is_workaround_redundant(
    mock_issue_checker__none: Mock, mock_issue_checker__true: Mock
) -> None:
    manager = IssueCheckerManager(
        issue_checkers=[mock_issue_checker__none, mock_issue_checker__true]
    )
    is_redundant = manager.is_workaround_redundant(WORKAROUND)
    mock_issue_checker__none.is_issue_resolved.assert_called_once_with(WORKAROUND.url)
    mock_issue_checker__true.is_issue_resolved.assert_called_once_with(WORKAROUND.url)
    assert is_redundant is True


def test_issue_checker_manager__is_workaround_redundant__no_checkers() -> None:
    manager = IssueCheckerManager(issue_checkers=[])
    with pytest.raises(UnknownIssueResolutionError):
        _ = manager.is_workaround_redundant(WORKAROUND)


def test_issue_checker_manager__is_workaround_redundant__error(
    mock_issue_checker__none: Mock,
) -> None:
    manager = IssueCheckerManager(issue_checkers=[mock_issue_checker__none])
    with pytest.raises(UnknownIssueResolutionError):
        _ = manager.is_workaround_redundant(WORKAROUND)
    mock_issue_checker__none.is_issue_resolved.assert_called_once_with(WORKAROUND.url)


@pytest.fixture
def _set_token_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GITHUB_AUTHENTICATION_ENV_VAR, GITHUB_TOKEN)
    monkeypatch.setenv(GITLAB_AUTHENTICATION_ENV_VAR, GITLAB_TOKEN)


@pytest.mark.usefixtures("_set_token_environment_variables")
def test_issue_checker_manager__from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "workaround_tracker.issue_checker._manager.GithubIssueChecker",
        mock_github_issue_checker := Mock(spec=GithubIssueChecker),
    )
    monkeypatch.setattr(
        "workaround_tracker.issue_checker._manager.GitlabIssueChecker",
        mock_gitlab_issue_checker := Mock(spec=GitlabIssueChecker),
    )
    _ = IssueCheckerManager.from_config(
        [ISSUE_TRACKER_CONFIG_GITHUB, ISSUE_TRACKER_CONFIG_GITLAB]
    )
    mock_github_issue_checker.assert_called_once_with(
        url=f"https://{GITHUB_HOSTNAME}",
        token=GITHUB_TOKEN,
    )
    mock_gitlab_issue_checker.assert_called_once_with(
        url=f"https://{GITLAB_HOSTNAME}",
        token=GITLAB_TOKEN,
    )


@pytest.mark.integration_test
@pytest.mark.usefixtures("_set_token_environment_variables")
def test_issue_checker__integration(
    requests_mock: RequestsMock,
) -> None:
    requests_mock.get(
        GITHUB_API_ISSUE_URL,
        json={"state": "closed"},
        request_headers=GITHUB_REQUEST_HEADERS,
        headers={"Content-Type": GITHUB_MEDIA_TYPE},
    )
    manager = IssueCheckerManager.from_config([ISSUE_TRACKER_CONFIG_GITHUB])
    is_redundant = manager.is_workaround_redundant(WORKAROUND)
    assert is_redundant
