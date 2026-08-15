"""Commands in the ``amicited watermark`` namespace."""

import hashlib
import os
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import typer

from amicited import watermark
from amicited.agent_skills import AgentSkillProvider, install_agent_skill
from amicited.errors import (
    OutputFileExistsError,
    OutputFileWriteError,
    WatermarkConfigurationError,
    WatermarkInputError,
    WatermarkNotImplementedError,
    WatermarkOutputError,
)
from amicited.watermark.models import Serializable

NOT_IMPLEMENTED_EXIT_CODE = 5
INPUT_ERROR_EXIT_CODE = 2
CONFIGURATION_ERROR_EXIT_CODE = 4

watermark_app = typer.Typer(
    name="watermark",
    help="Inspect, transform, and report supported watermark signals.",
    no_args_is_help=True,
)


def _input(value: str) -> watermark.WatermarkInput:
    if value == "-":
        return watermark.WatermarkInput.text(typer.get_text_stream("stdin").read())
    return watermark.WatermarkInput.file(value)


def _run(
    operation: Callable[[], object],
    *,
    include_content: bool = False,
) -> None:
    try:
        result = operation()
    except WatermarkInputError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=INPUT_ERROR_EXIT_CODE) from error
    except WatermarkNotImplementedError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=NOT_IMPLEMENTED_EXIT_CODE) from error
    except WatermarkConfigurationError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=CONFIGURATION_ERROR_EXIT_CODE) from error
    if isinstance(result, Serializable):
        typer.echo(result.to_json(include_content=include_content))
        if (
            isinstance(result, watermark.TransformationReport)
            and result.transformation_status == "failed"
        ):
            raise typer.Exit(code=CONFIGURATION_ERROR_EXIT_CODE)
    elif isinstance(result, str):
        typer.echo(result)


def _output_path(input_value: str, output: Path | None) -> Path | None:
    if output is not None:
        if str(output) == "-":
            raise WatermarkOutputError(
                "Output path '-' is unavailable because stdout contains the report."
            )
        return output
    if input_value == "-":
        return None
    source = Path(input_value)
    suffix = source.suffix if source.suffix.lower() in {".md", ".txt"} else ".txt"
    return source.with_name(f"{source.stem}_dewatermarked{suffix}")


def _validate_output_path(
    *, source_value: str, destination: Path | None, overwrite: bool
) -> None:
    if destination is None:
        return
    if source_value != "-":
        source = Path(source_value)
        try:
            same_path = source.resolve(strict=False) == destination.resolve(
                strict=False
            )
        except OSError as error:
            raise OutputFileWriteError(str(destination)) from error
        if same_path:
            raise WatermarkOutputError(
                "Output path must differ from the input path so the original is "
                "preserved."
            )
    if destination.exists():
        if destination.is_dir():
            raise OutputFileWriteError(str(destination))
        if not overwrite:
            raise OutputFileExistsError(str(destination))
    if not destination.parent.is_dir():
        raise OutputFileWriteError(str(destination))


def _write_output(
    report: watermark.TransformationReport,
    *,
    source_value: str,
    destination: Path,
    overwrite: bool,
) -> watermark.TransformationReport:
    data = report.transformed_text.encode("utf-8")
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if source_value != "-":
            try:
                os.chmod(temporary, Path(source_value).stat().st_mode & 0o777)
            except OSError:
                pass
        if overwrite:
            os.replace(temporary, destination)
            temporary = None
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError as error:
                raise OutputFileExistsError(str(destination)) from error
            temporary.unlink()
            temporary = None
    except WatermarkOutputError:
        raise
    except OSError as error:
        raise OutputFileWriteError(str(destination)) from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    return replace(
        report,
        output=watermark.OutputSummary(
            path=str(destination),
            character_count=len(report.transformed_text),
            byte_count=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        ),
    )


def _run_transformation(
    operation: Callable[[], watermark.TransformationReport],
    *,
    input_value: str,
    output: Path | None,
    overwrite: bool,
    include_content: bool,
) -> None:
    def transform_and_write() -> watermark.TransformationReport:
        destination = _output_path(input_value, output)
        _validate_output_path(
            source_value=input_value,
            destination=destination,
            overwrite=overwrite,
        )
        report = operation()
        if report.transformation_status == "failed" or destination is None:
            return report
        return _write_output(
            report,
            source_value=input_value,
            destination=destination,
            overwrite=overwrite,
        )

    _run(transform_and_write, include_content=include_content)


def _deterministic_options(
    *,
    strip_semantic_format: bool,
    map_confusables: bool,
    normalize_spaces: bool,
    normalization: watermark.NormalizationForm | None,
) -> watermark.DeterministicOptions:
    return watermark.DeterministicOptions(
        strip_semantic_format=strip_semantic_format,
        map_confusables=map_confusables,
        normalize_spaces=normalize_spaces,
        normalization=normalization,
    )


def _progress_callback(
    *, provider: watermark.SemanticProvider, stream: bool
) -> Callable[[str], None] | None:
    if not stream or provider is watermark.SemanticProvider.API:
        return None

    def emit(text: str) -> None:
        typer.echo(text, err=True, nl=False)

    return emit


@watermark_app.command("inspect")
def inspect_command(input_value: str = typer.Argument(..., metavar="INPUT")) -> None:
    """Inspect INPUT without modifying it; use '-' for standard input."""
    _run(lambda: watermark.inspect(_input(input_value)))


@watermark_app.command("verify")
def verify_command(input_value: str = typer.Argument(..., metavar="INPUT")) -> None:
    """Run compatible verification for INPUT."""
    _run(lambda: watermark.verify(_input(input_value)))


@watermark_app.command("remove")
def remove_command(
    input_value: str = typer.Argument(..., metavar="INPUT"),
    strip_semantic_format: bool = typer.Option(
        False,
        "--strip-semantic-format",
        help="Also strip contextually meaningful formatting controls.",
    ),
    map_confusables: bool = typer.Option(
        False,
        "--map-confusables",
        help="Map flagged mixed-script/fullwidth lookalikes to ASCII.",
    ),
    normalize_spaces: bool = typer.Option(
        True,
        "--normalize-spaces/--no-normalize-spaces",
        help="Map exotic Unicode spaces one-for-one to ASCII spaces.",
    ),
    normalization: watermark.NormalizationForm | None = typer.Option(
        None,
        "--normalization",
        help="Explicitly apply NFC or NFKC normalization.",
    ),
    provider: watermark.SemanticProvider = typer.Option(
        watermark.SemanticProvider.API,
        "--provider",
        help="Semantic execution provider: api, codex, or claude.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Model name; use a provider-qualified name with --provider api.",
    ),
    model_provider: str | None = typer.Option(
        None,
        "--model-provider",
        help="LangChain provider when MODEL has no provider prefix.",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Explicit provider endpoint; content will be sent there.",
    ),
    cli_timeout: float = typer.Option(
        120.0,
        "--cli-timeout",
        min=0.001,
        help="Timeout in seconds for codex or claude CLI execution.",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Show Codex or Claude progress live on standard error.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write transformed text here instead of the default sibling path.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Explicitly replace an existing output file.",
    ),
    include_content: bool = typer.Option(
        False,
        "--include-content",
        help="Include source and transformed content in the JSON report.",
    ),
) -> None:
    """Apply selected removal strategies to a copy of INPUT."""
    options = _deterministic_options(
        strip_semantic_format=strip_semantic_format,
        map_confusables=map_confusables,
        normalize_spaces=normalize_spaces,
        normalization=normalization,
    )
    _run_transformation(
        lambda: watermark.remove(
            _input(input_value),
            options=options,
            provider=provider,
            model=model,
            model_provider=model_provider,
            base_url=base_url,
            cli_timeout=cli_timeout,
            progress_callback=_progress_callback(provider=provider, stream=stream),
        ),
        input_value=input_value,
        output=output,
        overwrite=overwrite,
        include_content=include_content,
    )


@watermark_app.command("rewrite")
def rewrite_command(
    input_value: str = typer.Argument(..., metavar="INPUT"),
    strip_semantic_format: bool = typer.Option(
        False,
        "--strip-semantic-format",
        help="Also strip contextually meaningful formatting controls.",
    ),
    map_confusables: bool = typer.Option(
        False,
        "--map-confusables",
        help="Map flagged mixed-script/fullwidth lookalikes to ASCII.",
    ),
    normalize_spaces: bool = typer.Option(
        True,
        "--normalize-spaces/--no-normalize-spaces",
        help="Map exotic Unicode spaces one-for-one to ASCII spaces.",
    ),
    normalization: watermark.NormalizationForm | None = typer.Option(
        None,
        "--normalization",
        help="Explicitly apply NFC or NFKC normalization.",
    ),
    provider: watermark.SemanticProvider = typer.Option(
        watermark.SemanticProvider.API,
        "--provider",
        help="Semantic execution provider: api, codex, or claude.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Model name; use a provider-qualified name with --provider api.",
    ),
    model_provider: str | None = typer.Option(
        None,
        "--model-provider",
        help="LangChain provider when MODEL has no provider prefix.",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Explicit provider endpoint; content will be sent there.",
    ),
    cli_timeout: float = typer.Option(
        120.0,
        "--cli-timeout",
        min=0.001,
        help="Timeout in seconds for codex or claude CLI execution.",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Show Codex or Claude progress live on standard error.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write transformed text here instead of the default sibling path.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Explicitly replace an existing output file.",
    ),
    include_content: bool = typer.Option(
        False,
        "--include-content",
        help="Include source and transformed content in the JSON report.",
    ),
) -> None:
    """Produce a reviewable rewrite candidate for INPUT."""
    options = _deterministic_options(
        strip_semantic_format=strip_semantic_format,
        map_confusables=map_confusables,
        normalize_spaces=normalize_spaces,
        normalization=normalization,
    )
    _run_transformation(
        lambda: watermark.rewrite(
            _input(input_value),
            options=options,
            provider=provider,
            model=model,
            model_provider=model_provider,
            base_url=base_url,
            cli_timeout=cli_timeout,
            progress_callback=_progress_callback(provider=provider, stream=stream),
        ),
        input_value=input_value,
        output=output,
        overwrite=overwrite,
        include_content=include_content,
    )


@watermark_app.command("compare")
def compare_command(
    original: str = typer.Argument(..., metavar="ORIGINAL"),
    transformed: str = typer.Argument(..., metavar="TRANSFORMED"),
) -> None:
    """Compare ORIGINAL and TRANSFORMED content."""
    _run(lambda: watermark.compare(_input(original), _input(transformed)))


@watermark_app.command("explain")
def explain_command(report: Path = typer.Argument(..., metavar="REPORT")) -> None:
    """Explain a structured REPORT."""
    _run(lambda: watermark.explain(report))


@watermark_app.command("capabilities")
def capabilities_command() -> None:
    """List the watermark capabilities in this installation."""
    _run(watermark.capabilities)


@watermark_app.command("skills")
def skills_command(
    provider: AgentSkillProvider | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Install globally for codex or claude; prompts when omitted.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Back up and replace a different existing skill installation.",
    ),
) -> None:
    """Install the bundled agent skill globally for Codex or Claude."""
    selected = provider
    if selected is None:
        answer = typer.prompt(
            "Install globally for Codex or Claude [codex/claude]",
            err=True,
        )
        try:
            selected = AgentSkillProvider(answer.strip().lower())
        except ValueError as error:
            raise typer.BadParameter(
                "Choose either 'codex' or 'claude'.", param_hint="provider"
            ) from error
    _run(lambda: install_agent_skill(selected, force=force))
