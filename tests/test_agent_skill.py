from pathlib import Path

SKILL = Path(__file__).parents[1] / "skills" / "amicited-watermarks" / "SKILL.md"
OPENAI_METADATA = SKILL.parent / "agents" / "openai.yaml"


def test_agent_skill_has_required_identity_and_workflow() -> None:
    text = SKILL.read_text(encoding="utf-8")
    compact = " ".join(text.split())

    assert text.startswith("---\nname: amicited-watermarks\n")
    assert "amicited watermark capabilities" in text
    assert "## Use file-first input" in text
    assert (
        "Put every article or other long text in a UTF-8 `.md` or `.txt` file" in text
    )
    assert "Pass only the file path as the positional CLI input" in text
    assert "Do not pipe long text to `amicited ... -`" in text
    assert "amicited watermark inspect article.md" in text
    assert "Semantic rewriting is the expected default for articles" in compact
    assert "Do not treat a no-change deterministic report as completion" in compact
    assert "ask the user to choose `codex`, `claude`, or `api`" in compact
    assert "amicited watermark rewrite article.md --provider codex" in compact
    assert "amicited watermark rewrite article.md --provider claude" in compact
    assert "--provider api --model PROVIDER:MODEL" in compact
    assert (
        "Never run `amicited watermark rewrite ARTICLE` without an explicit" in compact
    )
    assert "`article_dewatermarked.md`" in compact
    assert "The original `article.md` remains unchanged" in compact
    assert "amicited watermark verify article_dewatermarked.md" in text
    assert "obtain user\n   confirmation" in text
    assert "Never rewrite this as\n  `not_detected`" in text
    assert "This never\n  establishes human authorship" in text
    assert "Never claim OpenAI, Anthropic, Gemini" in text


def test_agent_skill_has_codex_interface_metadata() -> None:
    metadata = OPENAI_METADATA.read_text(encoding="utf-8")

    assert 'display_name: "AmICited Watermarks"' in metadata
    assert 'short_description: "Semantically rewrite text files safely"' in metadata
    assert "semantic rewrite of my article file" in metadata
    assert "explicitly selected provider" in metadata
    assert "$amicited-watermarks" in metadata
