import logging
import typing

from workaround_tracker.common import WORKAROUND_COMMENT_PREFIX

from ._base import CodeScanner, find_first_url_in_text

LOGGER = logging.getLogger(__name__)


class PythonCodeScanner(CodeScanner):
    def get_file_suffixes(self) -> set[str]:
        return {".py"}

    def scan_file(
        self, file: typing.IO[str]
    ) -> typing.Generator[tuple[int, str], None, None]:
        for line_index, line in enumerate(file.readlines()):
            line_number = line_index + 1
            if line.lstrip().startswith(f"# {WORKAROUND_COMMENT_PREFIX}"):
                LOGGER.debug("Found workaround on L%s", line_number)
                url: typing.Optional[str] = find_first_url_in_text(line)
                if url is not None:
                    LOGGER.debug("Found url: %s", url)
                    yield line_number, url
