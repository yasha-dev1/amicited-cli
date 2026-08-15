"""Top-level AmICited command tree."""

from typing import Never

import typer

from amicited.cli.watermark.app import watermark_app

app = typer.Typer(
    name="amicited",
    help="AmICited command-line interface.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
app.add_typer(watermark_app, name="watermark")


def main() -> Never:
    """Run the installed AmICited command."""
    app()
    raise SystemExit(0)
