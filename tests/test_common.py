from pathlib import Path

import pytest

from workaround_tracker.common import AuthenticationConfig, Config, IssueTrackerConfig


@pytest.mark.parametrize(
    "filename, expected",
    [
        (
            "config_0.yaml",
            Config(
                scanners=["python"],
                issue_trackers=[
                    IssueTrackerConfig(
                        kind="github",
                        host="github.com",
                        authentication=AuthenticationConfig(env="GITHUB_TOKEN"),
                    ),
                    IssueTrackerConfig(
                        kind="github",
                        host="local.github",
                        authentication=AuthenticationConfig(env="LOCAL_GITHUB_TOKEN"),
                    ),
                    IssueTrackerConfig(
                        kind="gitlab",
                        host="gitlab.com",
                        authentication=AuthenticationConfig(env="GITLAB_TOKEN"),
                    ),
                ],
            ),
        ),
        (
            "config_1.yaml",
            Config(
                scanners=["python"],
                issue_trackers=[
                    IssueTrackerConfig(
                        kind="gitlab",
                        host="gitlab.com",
                        authentication=AuthenticationConfig(env="GITLAB_TOKEN"),
                    ),
                    IssueTrackerConfig(
                        kind="gitlab",
                        host="local.gitlab",
                        authentication=AuthenticationConfig(env="LOCAL_GITLAB_TOKEN"),
                    ),
                ],
            ),
        ),
    ],
)
def test_config_from_yaml_file(filename: str, expected: Config) -> None:
    filepath = Path(__file__).parent / "data" / "config" / filename
    actual = Config.from_yaml_file(filepath)
    assert actual == expected
