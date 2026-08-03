"""Coordinate reference system validation."""

import re
from dataclasses import dataclass

_EPSG_IDENTIFIER = re.compile(r"^EPSG\s*:\s*([1-9][0-9]*)$", re.IGNORECASE)
_MAX_EPSG_CODE = 999_999


class CoordinateReferenceSystemError(ValueError):
    """Base error for coordinate reference system failures."""


class CrsValidationError(CoordinateReferenceSystemError):
    """Raised when a CRS identifier cannot be safely interpreted."""


class MissingCoordinateReferenceSystemError(CoordinateReferenceSystemError):
    """Raised when spatial data has no coordinate reference system."""


class UnrecognizedCoordinateReferenceSystemError(CoordinateReferenceSystemError):
    """Raised when a CRS cannot be resolved by the configured CRS service."""


class NonMetricCoordinateReferenceSystemError(CoordinateReferenceSystemError):
    """Raised when a metric spatial operation is requested in a non-metric CRS."""


class CoordinateTransformationError(CoordinateReferenceSystemError):
    """Raised when geometry cannot be transformed between coordinate systems."""


@dataclass(frozen=True, slots=True)
class CrsDefinition:
    """Library-neutral description of a recognized coordinate system."""

    identifier: str
    is_geographic: bool
    axis_units: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "identifier", normalize_crs(self.identifier))

    @property
    def is_metric(self) -> bool:
        """Return whether all axes use metres in a non-geographic CRS."""
        metric_units = {"metre", "metres", "meter", "meters"}
        return (
            not self.is_geographic
            and bool(self.axis_units)
            and all(unit.casefold() in metric_units for unit in self.axis_units)
        )


def normalize_crs(crs: str) -> str:
    """Validate and return a canonical ``EPSG:<code>`` identifier.

    This validates the identifier and its numeric range, not its presence in the
    external EPSG registry. Registry lookup belongs to a future GIS adapter.
    """
    match = _EPSG_IDENTIFIER.fullmatch(crs.strip())
    if match is None:
        raise CrsValidationError("crs must use an unambiguous EPSG:<code> identifier")

    code = int(match.group(1))
    if code > _MAX_EPSG_CODE:
        raise CrsValidationError(f"EPSG code must not exceed {_MAX_EPSG_CODE}")

    return f"EPSG:{code}"
