"""Safe installation of AmICited's bundled agent skill."""

from __future__ import annotations

import hashlib
import os
import shutil
import sysconfig
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from amicited.errors import WatermarkConfigurationError
from amicited.watermark.models import Serializable

SCHEMA_VERSION = "1.0"
SKILL_NAME = "amicited-watermarks"


class AgentSkillProvider(StrEnum):
    """Agent products supported by the global skill installer."""

    CODEX = "codex"
    CLAUDE = "claude"


class SkillInstallationStatus(StrEnum):
    """Stable outcomes returned by the skill installer."""

    INSTALLED = "installed"
    ALREADY_INSTALLED = "already_installed"
    UPDATED = "updated"


class SkillInstallationError(WatermarkConfigurationError):
    """Raised when an agent skill cannot be installed safely."""


@dataclass(frozen=True, slots=True)
class SkillInstallationReport(Serializable):
    """Machine-readable result of one global skill installation."""

    schema_version: str
    tool_version: str
    operation: str
    started_at: str
    completed_at: str
    provider: AgentSkillProvider
    scope: str
    status: SkillInstallationStatus
    skill_name: str
    source: str
    destination: str
    backup_path: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _tool_version() -> str:
    try:
        return version("amicited")
    except PackageNotFoundError:  # pragma: no cover - source tree fallback
        return "0.0.0"


def _bundled_skill_path() -> Path:
    repository_copy = Path(__file__).resolve().parents[2] / "skills" / SKILL_NAME
    installed_data_copy = Path(sysconfig.get_path("data")) / SKILL_NAME
    for candidate in (repository_copy, installed_data_copy):
        if (candidate / "SKILL.md").is_file():
            return candidate
    raise SkillInstallationError(
        "The bundled amicited-watermarks skill is missing from this installation. "
        "Reinstall or upgrade amicited."
    )


def _destination(provider: AgentSkillProvider, home: Path) -> Path:
    if provider is AgentSkillProvider.CODEX:
        return home / ".agents" / "skills" / SKILL_NAME
    return home / ".claude" / "skills" / SKILL_NAME


def _manifest(root: Path) -> dict[str, str]:
    try:
        actual_root = root.resolve(strict=True) if root.is_symlink() else root
    except OSError as error:
        raise SkillInstallationError(f"Unable to read agent skill: {root}") from error
    if not actual_root.is_dir():
        raise SkillInstallationError(f"Agent skill path is not a directory: {root}")

    manifest: dict[str, str] = {}
    try:
        for item in sorted(actual_root.rglob("*")):
            if item.is_symlink():
                raise SkillInstallationError(
                    f"Agent skill contains an unsupported symbolic link: {item}"
                )
            if item.is_file():
                relative = item.relative_to(actual_root).as_posix()
                manifest[relative] = hashlib.sha256(item.read_bytes()).hexdigest()
            elif not item.is_dir():
                raise SkillInstallationError(
                    f"Agent skill contains an unsupported file type: {item}"
                )
    except SkillInstallationError:
        raise
    except OSError as error:
        raise SkillInstallationError(f"Unable to read agent skill: {root}") from error
    return manifest


def _validate_source(source: Path) -> None:
    skill_file = source / "SKILL.md"
    if not skill_file.is_file():
        raise SkillInstallationError(
            f"Bundled agent skill is invalid because SKILL.md is missing: {source}"
        )
    _manifest(source)


def _backup_destination(destination: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = destination.with_name(f"{destination.name}.backup-{stamp}")
    counter = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = destination.with_name(
            f"{destination.name}.backup-{stamp}-{counter}"
        )
        counter += 1
    return candidate


def install_agent_skill(
    provider: AgentSkillProvider,
    *,
    force: bool = False,
    home: Path | None = None,
    source: Path | None = None,
) -> SkillInstallationReport:
    """Install the bundled skill globally for Codex or Claude.

    Existing matching content is left untouched. Differing content requires
    ``force=True`` and is moved to a timestamped sibling backup before update.
    """
    started_at = _now()
    selected_provider = AgentSkillProvider(provider)
    source_path = source if source is not None else _bundled_skill_path()
    home_path = home if home is not None else Path.home()
    destination = _destination(selected_provider, home_path)

    _validate_source(source_path)
    source_manifest = _manifest(source_path)
    destination_exists = destination.exists() or destination.is_symlink()
    if destination_exists:
        try:
            matching = _manifest(destination) == source_manifest
        except SkillInstallationError:
            matching = False
        if matching:
            return SkillInstallationReport(
                schema_version=SCHEMA_VERSION,
                tool_version=_tool_version(),
                operation="skills",
                started_at=started_at,
                completed_at=_now(),
                provider=selected_provider,
                scope="global",
                status=SkillInstallationStatus.ALREADY_INSTALLED,
                skill_name=SKILL_NAME,
                source=str(source_path),
                destination=str(destination),
            )
        if not force:
            raise SkillInstallationError(
                f"A different skill already exists at {destination}. "
                "Use --force to preserve it as a backup and install this version."
            )

    backup: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f".{SKILL_NAME}.", dir=destination.parent
        ) as temporary_directory:
            staged = Path(temporary_directory) / SKILL_NAME
            shutil.copytree(source_path, staged)
            if destination_exists:
                backup = _backup_destination(destination)
                os.replace(destination, backup)
            try:
                os.replace(staged, destination)
            except OSError:
                if backup is not None and not destination.exists():
                    os.replace(backup, destination)
                    backup = None
                raise
    except OSError as error:
        raise SkillInstallationError(
            f"Unable to install the agent skill safely at {destination}."
        ) from error

    status = (
        SkillInstallationStatus.UPDATED
        if backup is not None
        else SkillInstallationStatus.INSTALLED
    )
    warnings = (
        (f"The previous skill was preserved at {backup}.",)
        if backup is not None
        else ()
    )
    return SkillInstallationReport(
        schema_version=SCHEMA_VERSION,
        tool_version=_tool_version(),
        operation="skills",
        started_at=started_at,
        completed_at=_now(),
        provider=selected_provider,
        scope="global",
        status=status,
        skill_name=SKILL_NAME,
        source=str(source_path),
        destination=str(destination),
        backup_path=str(backup) if backup is not None else None,
        warnings=warnings,
    )


__all__ = [
    "AgentSkillProvider",
    "SkillInstallationError",
    "SkillInstallationReport",
    "SkillInstallationStatus",
    "install_agent_skill",
]
