from pathlib import Path

SKILL = Path(__file__).parents[1] / "skills" / "amicited-watermarks" / "SKILL.md"
OPENAI_METADATA = SKILL.parent / "agents" / "openai.yaml"


def test_agent_skill_has_required_identity_and_workflow() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert text.startswith("---\nname: amicited-watermarks\n")
    assert "amicited watermark capabilities" in text
    assert "## Use file-first input" in text
    assert (
        "Put every article or other long text in a UTF-8 `.md` or `.txt` file" in text
    )
    assert "Pass only the file path as the positional CLI input" in text
    assert "Do not pipe long text to `amicited ... -`" in text
    assert "amicited watermark inspect article.md" in text
    assert "amicited watermark verify article_dewatermarked.md" in text
    assert "obtain user\n   confirmation" in text
    assert "Never rewrite this as\n  `not_detected`" in text
    assert "This never\n  establishes human authorship" in text
    assert "Never claim OpenAI, Anthropic, Gemini" in text


def test_agent_skill_has_codex_interface_metadata() -> None:
    metadata = OPENAI_METADATA.read_text(encoding="utf-8")

    assert 'display_name: "AmICited Watermarks"' in metadata
    assert 'short_description: "Inspect and safely rewrite text files"' in metadata
    assert "inspect my article file" in metadata
    assert "$amicited-watermarks" in metadata
