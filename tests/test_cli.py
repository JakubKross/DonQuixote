import pytest

from renewable_planner import __version__
from renewable_planner.cli import main


def test_cli_displays_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"DonQuixote {__version__}"
