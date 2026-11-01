"""Exception hierarchy and process exit codes.

Every failure mode in proxyfetch maps to a stable, documented exit code so
that humans and AI agents can branch on the outcome without parsing text.
"""
from __future__ import annotations

EXIT_OK = 0            # results collected
EXIT_NO_RESULTS = 1    # ran, but zero items extracted
EXIT_USAGE = 2         # bad CLI usage (argparse convention)
EXIT_NO_PROXIES = 3    # supply stage could not find a single working proxy
EXIT_ERROR = 4         # unexpected internal error
EXIT_INTERRUPTED = 130 # SIGINT (partial results may still have been saved)


class ProxyFetchError(Exception):
    """Base class for all expected proxyfetch failures.

    Carries an optional machine-readable ``code`` and a user-facing ``hint``
    that the CLI prints as an actionable next step.
    """

    exit_code = EXIT_ERROR

    def __init__(self, message: str, *, hint: str | None = None,
                 code: str = "internal_error") -> None:
        super().__init__(message)
        self.hint = hint
        self.code = code


class ConfigError(ProxyFetchError):
    """Invalid configuration / CLI usage that argparse cannot detect."""

    exit_code = EXIT_USAGE

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message, hint=hint, code="config_error")


class NoProxiesError(ProxyFetchError):
    """The supply stage harvested/verified zero usable proxies."""

    exit_code = EXIT_NO_PROXIES

    def __init__(self, message: str = "no working proxy could be sourced",
                 *, hint: str | None = None) -> None:
        super().__init__(message, hint=hint, code="no_proxies")


class NoResultsError(ProxyFetchError):
    """The pipeline ran but extracted zero items from the target."""

    exit_code = EXIT_NO_RESULTS

    def __init__(self, message: str = "no items could be extracted",
                 *, hint: str | None = None) -> None:
        super().__init__(message, hint=hint, code="no_results")


class BudgetExceeded(ProxyFetchError):
    """Wall-clock budget exhausted (usually surfaced as a warning, not fatal)."""

    exit_code = EXIT_ERROR

    def __init__(self, message: str = "time budget exhausted") -> None:
        super().__init__(message, code="budget_exceeded")
