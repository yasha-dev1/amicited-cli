from importlib import import_module

PRIVATE_SUBSYSTEMS = {
    "capabilities",
    "comparison",
    "explanation",
    "file_safety",
    "inspection",
    "removal",
    "rewrite",
    "verification",
}


def test_cli_and_private_watermark_subsystems_have_dedicated_packages() -> None:
    import_module("amicited.cli.watermark.app")

    for subsystem in PRIVATE_SUBSYSTEMS:
        import_module(f"amicited.watermark._internal.{subsystem}")
