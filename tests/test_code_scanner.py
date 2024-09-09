import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, call

import freezegun
import pytest

from workaround_tracker.code_scanner._base import CodeScanner, find_first_url_in_text
from workaround_tracker.code_scanner._manager import (
    CodeScannerCache,
    CodeScannerManager,
    FileScanCache,
    NoCodeScannersError,
    OverlappingCodeScannersError,
)
from workaround_tracker.code_scanner._python import PythonCodeScanner
from workaround_tracker.common import Workaround

DATA_PATH = Path(__file__).parent / "data"
CODE_PATH = DATA_PATH / "code"
PYTHON_FILE_IN_ROOT = CODE_PATH / "code.py"
PYTHON_FILE_IN_SUBDIR = CODE_PATH / "subdir" / "file.py"
CACHE_PATH = DATA_PATH / "cache"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Here is a url: https://hello/world", "https://hello/world"),
        ("Also, http://bye/world is another url", "http://bye/world"),
        ("No url here!", None),
    ],
)
def test_find_first_url_in_text(text: str, expected: Optional[str]) -> None:
    assert find_first_url_in_text(text) == expected


@pytest.fixture
def mock_find_first_url_in_text(monkeypatch: pytest.MonkeyPatch) -> Mock:
    mocked_function = Mock(
        spec=find_first_url_in_text,
        side_effect=["http://first/url/1", None, "http://first/url/2"],
    )
    monkeypatch.setattr(
        "workaround_tracker.code_scanner._python.find_first_url_in_text",
        mocked_function,
    )
    return mocked_function


@pytest.fixture
def python_code_scanner() -> PythonCodeScanner:
    return PythonCodeScanner()


def test_python_file_suffixes(python_code_scanner: PythonCodeScanner) -> None:
    assert python_code_scanner.get_file_suffixes() == {".py"}


def test_python_scan_file(
    python_code_scanner: PythonCodeScanner,
    mock_find_first_url_in_text: Mock,
    tmp_path: Path,
) -> None:
    file_to_scan = tmp_path / "file.py"
    with file_to_scan.open(mode="x") as filehandle:
        filehandle.write(
            "".join(
                [
                    "\n",
                    workaround_line_1 := "# WORKAROUND: for issue http://fake/url\n",
                    workaround_line_2 := "# WORKAROUND: no url here\n",
                    workaround_line_3
                    := "# WORKAROUND: for issue http://other/fake/url\n",
                    "\n",
                ]
            )
        )

    with file_to_scan.open() as filehandle:
        workarounds = list(python_code_scanner.scan_file(filehandle))

    assert mock_find_first_url_in_text.mock_calls == [
        call(workaround_line_1),
        call(workaround_line_2),
        call(workaround_line_3),
    ]
    assert workarounds == [
        (2, "http://first/url/1"),
        (4, "http://first/url/2"),
    ]


@pytest.fixture
def mock_python_code_scanner() -> Mock:
    return Mock(
        spec=PythonCodeScanner,
        get_file_suffixes=Mock(return_value={".py"}),
        scan_file=Mock(side_effect=[iter([(1, "hello")]), iter([(2, "world")])]),
    )


@pytest.fixture
def mock_code_scanners(mock_python_code_scanner: CodeScanner) -> list[CodeScanner]:
    return [
        mock_python_code_scanner,
        Mock(spec=CodeScanner, get_file_suffixes=Mock(return_value={".pyc"})),
    ]


@pytest.fixture
def mock_cache() -> CodeScannerCache:
    return Mock(spec=CodeScannerCache)


def test_code_scanner_manager__no_code_scanners() -> None:
    with pytest.raises(NoCodeScannersError):
        _ = CodeScannerManager(code_scanners=[])


def test_code_scanner_manager__overlapping_file_suffixes(
    mock_python_code_scanner: Mock,
) -> None:
    with pytest.raises(OverlappingCodeScannersError):
        _ = CodeScannerManager(
            code_scanners=[mock_python_code_scanner, mock_python_code_scanner]
        )


def test_code_scanner_manager__cache(
    mock_code_scanners: list[Mock], mock_cache: Mock
) -> None:
    manager = CodeScannerManager(code_scanners=mock_code_scanners, cache=mock_cache)
    assert manager.cache is mock_cache


@freezegun.freeze_time(time_to_freeze=datetime.fromtimestamp(1234.0, tz=timezone.utc))
def test_code_scanner_manager__scan_path(mock_python_code_scanner: Mock) -> None:
    manager = CodeScannerManager(code_scanners=[mock_python_code_scanner])
    assert manager.cache == CodeScannerCache(files={})

    workarounds = list(manager.scan_path(CODE_PATH))

    assert mock_python_code_scanner.scan_file.call_count == 2
    assert workarounds == [
        code_workaround := Workaround(file=PYTHON_FILE_IN_ROOT, line=1, url="hello"),
        file_workaround := Workaround(file=PYTHON_FILE_IN_SUBDIR, line=2, url="world"),
    ]
    assert manager.cache == CodeScannerCache(
        files={
            PYTHON_FILE_IN_ROOT: FileScanCache(
                workarounds=[code_workaround], timestamp=1234.0
            ),
            PYTHON_FILE_IN_SUBDIR: FileScanCache(
                workarounds=[file_workaround], timestamp=1234.0
            ),
        }
    )


def test_code_scanner_manager__scan_path__cached(
    mock_python_code_scanner: Mock,
) -> None:
    manager = CodeScannerManager(
        code_scanners=[mock_python_code_scanner],
        cache=CodeScannerCache(
            files={
                PYTHON_FILE_IN_ROOT: FileScanCache(
                    workarounds=[
                        Workaround(file=PYTHON_FILE_IN_ROOT, line=1, url="hello")
                    ],
                    timestamp=0.0,
                ),
                PYTHON_FILE_IN_SUBDIR: FileScanCache(
                    workarounds=[
                        Workaround(
                            file=CODE_PATH / "subdir" / "file.py", line=2, url="world"
                        )
                    ],
                    timestamp=time.time(),
                ),
            }
        ),
    )

    workarounds = list(manager.scan_path(CODE_PATH))

    assert mock_python_code_scanner.scan_file.call_count == 1
    assert workarounds == [
        Workaround(file=PYTHON_FILE_IN_ROOT, line=1, url="hello"),
        Workaround(file=PYTHON_FILE_IN_SUBDIR, line=2, url="world"),
    ]


CACHE_0_CONTENT = CodeScannerCache(
    files={
        Path("tests") / "data" / "code.py": FileScanCache(
            workarounds=[
                Workaround(
                    file=Path("tests") / "data" / "code.py",
                    line=3,
                    url="https://github.com/litestar-org/litestar/issues/3630",
                ),
                Workaround(
                    file=Path("tests") / "data" / "code.py",
                    line=4,
                    url="https://github.com/mam-dev/security-constraints/issues/32",
                ),
            ],
            timestamp=1724923993.2067041,
        ),
        Path("tests") / "test_code_scanner.py": FileScanCache(
            workarounds=[], timestamp=1724937291.112679
        ),
    }
)
CACHE_1_CONTENT = CodeScannerCache()


@pytest.mark.parametrize(
    "cache_file, expected",
    [
        ("cache_0.json", CACHE_0_CONTENT),
        ("cache_1.json", CACHE_1_CONTENT),
    ],
)
def test_code_scanner_cache__from_json(
    cache_file: str, expected: CodeScannerCache
) -> None:
    assert CodeScannerCache.from_json_file(CACHE_PATH / cache_file) == expected


@pytest.mark.parametrize(
    "cache, expected_matching_file",
    [
        (CACHE_0_CONTENT, "cache_0.json"),
        (CACHE_1_CONTENT, "cache_1.json"),
    ],
)
def test_code_scanner_cache__write_to_json_file(
    tmp_path: Path, cache: CodeScannerCache, expected_matching_file: str
) -> None:
    output_file = tmp_path / "cache.json"
    cache.write_to_json_file(output_file)
    with (
        output_file.open() as written_file,
        (CACHE_PATH / expected_matching_file).open() as matching_file,
    ):
        assert written_file.read() == matching_file.read()


@pytest.mark.integration_test
def test_code_scanner__integration() -> None:
    manager = CodeScannerManager(code_scanners=[PythonCodeScanner()])
    workarounds = list(manager.scan_path(CODE_PATH))
    assert workarounds == [
        Workaround(
            file=PYTHON_FILE_IN_ROOT,
            line=1,
            url="https://github.com/litestar-org/litestar/issues/3630",
        ),
        Workaround(
            file=PYTHON_FILE_IN_SUBDIR,
            line=3,
            url="https://github.com/mam-dev/security-constraints/issues/32",
        ),
    ]


def test_code_scanner_manager__from_scanner_strings(
    monkeypatch: pytest.MonkeyPatch, mock_python_code_scanner: Mock
) -> None:
    monkeypatch.setattr(
        "workaround_tracker.code_scanner._manager.PythonCodeScanner",
        mock_python_code_scanner_cls := Mock(return_value=mock_python_code_scanner),
    )
    _ = CodeScannerManager.from_scanner_strings(["python"])
    mock_python_code_scanner_cls.assert_called_once_with()


def test_code_scanner_manager__from_scanner_strings__no_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "workaround_tracker.code_scanner._base.CodeScanner",
        mock_code_scanner_cls := Mock(),
    )
    with pytest.raises(NoCodeScannersError):
        _ = CodeScannerManager.from_scanner_strings([])
    mock_code_scanner_cls.assert_not_called()
