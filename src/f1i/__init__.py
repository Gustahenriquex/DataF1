"""F1 Intelligence — strategic analytics platform for Formula 1."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("f1-intelligence")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0+unknown"
