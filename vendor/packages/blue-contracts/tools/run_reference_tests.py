"""Collect original tests unchanged; exclude only the leaked unittest factory helper."""
from pathlib import Path
import sys
import pytest
class Collection:
    def pytest_collection_modifyitems(self,config,items):
        # test_bex.py installs this factory as generated unittest methods, but also
        # leaves one module-level `test(self, e=...)` which is not a pytest test.
        skip=[item for item in items if Path(item.path).name == "test_bex.py"
              and item.name == "test" and getattr(item,"cls",None) is None]
        if skip:
            config.hook.pytest_deselected(items=skip)
            items[:]=[item for item in items if item not in skip]
raise SystemExit(pytest.main(["-q",sys.argv[1]],plugins=[Collection()]))
