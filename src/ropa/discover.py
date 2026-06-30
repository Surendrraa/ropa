"""Discover the individual tests in the given suite paths without running them.

Uses Robot Framework's own parser (TestSuiteBuilder) so discovery sees exactly
what `robot` would run — same parsing, same tags, no shelling out.
"""

from __future__ import annotations

from dataclasses import dataclass

from robot.running import TestSuiteBuilder


@dataclass(frozen=True)
class TestUnit:
    """One schedulable unit of work: a single test case."""

    longname: str          # e.g. "Login.Valid Credentials" (unique, for reporting)
    name: str              # the test case name, used with `robot --test`
    source: str            # the .robot file the test lives in

    @property
    def id(self) -> str:
        return self.longname


def discover(paths: list[str], includes: list[str] | None = None,
             excludes: list[str] | None = None) -> list[TestUnit]:
    """Return every test under `paths`, honoring --include/--exclude tag filters."""
    builder = TestSuiteBuilder(included_extensions=("robot",))
    suite = builder.build(*paths)
    if includes or excludes:
        suite.filter(included_tags=includes or None,
                     excluded_tags=excludes or None)

    units: list[TestUnit] = []
    for test in suite.all_tests:
        units.append(TestUnit(longname=test.longname,
                              name=test.name,
                              source=str(test.source)))
    return units
