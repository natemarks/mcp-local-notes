"""Scaffolding smoke test: every checked-in feature file is valid Gherkin.

Step definitions for these scenarios don't exist yet -- they land ticket by
ticket. This just proves the pytest-bdd toolchain is wired up correctly.
"""

import glob
import os

import pytest
from pytest_bdd.parser import FeatureParser

FEATURES_DIR = os.path.join(os.path.dirname(__file__), "..", "features")


def _feature_filenames() -> list[str]:
    paths = glob.glob(os.path.join(FEATURES_DIR, "*.feature"))
    return sorted(os.path.basename(path) for path in paths)


@pytest.mark.unit
@pytest.mark.parametrize("filename", _feature_filenames())
def test_feature_file_parses(filename: str) -> None:
    """Each .feature file is valid Gherkin with at least one scenario."""
    feature = FeatureParser(FEATURES_DIR, filename).parse()
    assert feature.scenarios
