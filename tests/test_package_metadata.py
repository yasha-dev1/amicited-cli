from importlib.metadata import distribution


def test_distribution_declares_the_cli_and_license() -> None:
    package = distribution("amicited")

    assert package.metadata["Name"] == "amicited"
    assert package.metadata["License-Expression"] == "MIT"
    assert package.metadata.get_all("License-File") == ["LICENSE"]
    assert any(
        entry.name == "amicited"
        and entry.group == "console_scripts"
        and entry.value == "amicited.cli.app:main"
        for entry in package.entry_points
    )
