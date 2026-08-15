from pathlib import Path

import pytest

from amicited.agent_skills import (
    AgentSkillProvider,
    SkillInstallationError,
    install_agent_skill,
)


def _skill_source(tmp_path: Path, *, body: str = "original") -> Path:
    source = tmp_path / "source" / "amicited-watermarks"
    (source / "agents").mkdir(parents=True)
    (source / "SKILL.md").write_text(body, encoding="utf-8")
    (source / "agents" / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")
    return source


@pytest.mark.parametrize(
    ("provider", "relative_destination"),
    [
        (AgentSkillProvider.CODEX, ".agents/skills/amicited-watermarks"),
        (AgentSkillProvider.CLAUDE, ".claude/skills/amicited-watermarks"),
    ],
)
def test_install_agent_skill_uses_provider_global_directory(
    tmp_path: Path,
    provider: AgentSkillProvider,
    relative_destination: str,
) -> None:
    source = _skill_source(tmp_path)
    home = tmp_path / "home"

    report = install_agent_skill(provider, home=home, source=source)

    destination = home / relative_destination
    assert report.operation == "skills"
    assert report.provider is provider
    assert report.scope == "global"
    assert report.status == "installed"
    assert report.destination == str(destination)
    assert report.backup_path is None
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "original"


def test_install_agent_skill_is_idempotent(tmp_path: Path) -> None:
    source = _skill_source(tmp_path)
    home = tmp_path / "home"
    install_agent_skill(AgentSkillProvider.CODEX, home=home, source=source)

    report = install_agent_skill(
        AgentSkillProvider.CODEX,
        home=home,
        source=source,
    )

    assert report.status == "already_installed"
    assert report.backup_path is None


def test_install_agent_skill_refuses_changed_destination_without_force(
    tmp_path: Path,
) -> None:
    source = _skill_source(tmp_path)
    home = tmp_path / "home"
    install_agent_skill(AgentSkillProvider.CODEX, home=home, source=source)
    destination = home / ".agents" / "skills" / "amicited-watermarks"
    (destination / "SKILL.md").write_text("user changes", encoding="utf-8")

    with pytest.raises(SkillInstallationError, match="--force"):
        install_agent_skill(AgentSkillProvider.CODEX, home=home, source=source)

    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "user changes"


def test_force_update_preserves_existing_skill_as_backup(tmp_path: Path) -> None:
    source = _skill_source(tmp_path, body="new version")
    home = tmp_path / "home"
    destination = home / ".claude" / "skills" / "amicited-watermarks"
    destination.mkdir(parents=True)
    (destination / "SKILL.md").write_text("old version", encoding="utf-8")

    report = install_agent_skill(
        AgentSkillProvider.CLAUDE,
        home=home,
        source=source,
        force=True,
    )

    assert report.status == "updated"
    assert report.backup_path is not None
    backup = Path(report.backup_path)
    assert backup.parent == destination.parent
    assert backup.name.startswith("amicited-watermarks.backup-")
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "old version"
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "new version"


def test_install_rejects_a_bundled_skill_without_skill_md(tmp_path: Path) -> None:
    source = tmp_path / "source" / "amicited-watermarks"
    source.mkdir(parents=True)

    with pytest.raises(SkillInstallationError, match="SKILL.md"):
        install_agent_skill(
            AgentSkillProvider.CODEX,
            home=tmp_path / "home",
            source=source,
        )
