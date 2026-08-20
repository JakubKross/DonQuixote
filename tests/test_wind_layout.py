from itertools import combinations

import pytest

from renewable_planner.domain import (
    AvailableArea,
    GridTurbineCandidateGenerator,
    TurbineSpacing,
    WindLayoutValidationError,
)

SQUARE = AvailableArea(
    exterior=((0, 0), (100, 0), (100, 100), (0, 100)),
)


def test_generator_returns_only_points_in_available_area() -> None:
    area = AvailableArea(
        exterior=((0, 0), (100, 0), (100, 100), (0, 100)),
        holes=(((40, 40), (60, 40), (60, 60), (40, 60)),),
    )

    positions = GridTurbineCandidateGenerator().generate(area, TurbineSpacing(20))

    assert all(area.contains((position.x_m, position.y_m)) for position in positions)
    assert (40.0, 40.0) not in {(position.x_m, position.y_m) for position in positions}


def test_generator_enforces_minimum_distance() -> None:
    positions = GridTurbineCandidateGenerator().generate(
        SQUARE, TurbineSpacing(25), grid_spacing_m=10
    )

    distances = [
        ((left.x_m - right.x_m) ** 2 + (left.y_m - right.y_m) ** 2) ** 0.5
        for left, right in combinations(positions, 2)
    ]

    assert positions
    assert min(distances) >= 25


def test_generator_is_deterministic() -> None:
    generator = GridTurbineCandidateGenerator()
    spacing = TurbineSpacing.from_rotor_diameters(5, 20)

    first = generator.generate(SQUARE, spacing)
    second = generator.generate(SQUARE, spacing)

    assert first == second
    assert first[0].x_m == 0
    assert first[0].y_m == 0


def test_spacing_can_be_defined_as_rotor_diameter_multiple() -> None:
    spacing = TurbineSpacing.from_rotor_diameters(6, 120)

    assert spacing.distance_m == 720


@pytest.mark.parametrize(
    ("multiplier", "rotor_diameter"),
    [(0, 100), (-1, 100), (5, 0), (float("inf"), 100)],
)
def test_spacing_rejects_invalid_rotor_parameters(multiplier: float, rotor_diameter: float) -> None:
    with pytest.raises(WindLayoutValidationError):
        TurbineSpacing.from_rotor_diameters(multiplier, rotor_diameter)
