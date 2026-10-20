"""Run unit test modules with one extra mutant switched on:
python3.12 unit_under_mutant.py "<mutant name>" tests.test_github ..."""
import sys
import unittest

sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
import extra_mutants  # noqa: E402
from validation import mutants  # noqa: E402

name, modules = sys.argv[1], sys.argv[2:]
mutant = extra_mutants.EXTRA[name]
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
with mutants.switched_on(mutant):
    result = unittest.TextTestRunner(verbosity=0, stream=open("/dev/null", "w")).run(suite)
print(name, "ran", result.testsRun, "failures", len(result.failures), "errors", len(result.errors))
for test, _ in result.failures + result.errors:
    print("  FAILED", test.id())
