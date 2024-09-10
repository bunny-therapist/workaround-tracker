import pytest

from workaround_tracker.main import setup_logging


@pytest.fixture(autouse=True, scope="session")
def _debug_logging() -> None:
    setup_logging(debug=True)
