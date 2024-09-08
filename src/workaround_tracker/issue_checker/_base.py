import abc
import typing


class IssueChecker(abc.ABC):
    @abc.abstractmethod
    def is_issue_resolved(
        self, url: str
    ) -> typing.Optional[bool]: ...  # pragma: no cover
