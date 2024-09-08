import abc
import re
import typing

_URL_REGEX = re.compile(r"https?://[^ \n]+")


def find_first_url_in_text(text: str) -> typing.Optional[str]:
    match: typing.Optional[re.Match[str]] = _URL_REGEX.search(text)
    if match is None:
        return None
    return match.group(0)


class CodeScanner(abc.ABC):
    """Scans code for workarounds."""

    @abc.abstractmethod
    def get_file_suffixes(self) -> set[str]:
        """Return the file suffixes handled by this CodeScanner."""

    @abc.abstractmethod
    def scan_file(
        self, file: typing.IO[str]
    ) -> typing.Generator[tuple[int, str], None, None]:
        """Scan file for workarounds.

        Args:
            file: The opened file to scan.

        Yields:
            (line number, issue url) strings, in order of appearance in the file.

        """
