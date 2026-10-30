"""The import pipeline's tests: python -m unittest discover -s scanimport/tests -t . from the
repository root. The archive's modules (exact, panjabi, neighbour) are imported where they are."""
from scanimport import archive_path

archive_path()
