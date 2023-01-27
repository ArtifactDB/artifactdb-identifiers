import sys

if sys.version_info >= (3, 8):
    from importlib.metadata import version, PackageNotFoundError
else:
    from importlib_metadata import version, PackageNotFoundError

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "artifactdb-identifiers"  # pylint: disable=invalid-name
    __version__ = version(dist_name)
except PackageNotFoundError as e:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
