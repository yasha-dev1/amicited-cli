<p align="center">
  <a href="https://www.amicited.com/">
    <img src="https://static.amicited.com/images/social-share.jpg" alt="AmICited — grow your brand on AI search" width="100%">
  </a>
</p>

<h1 align="center">AmICited CLI</h1>

<p align="center">
  <strong>Inspect, clean, verify, and safely rewrite AI-assisted text before you publish it.</strong>
</p>

<p align="center">
  <a href="https://www.amicited.com/"><img src="https://img.shields.io/badge/AmICited-AI_Search_Visibility-3b5cff" alt="AmICited website"></a>
  <a href="https://github.com/yasha-dev1/amicited-cli/actions/workflows/ci.yml"><img src="https://github.com/yasha-dev1/amicited-cli/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-0d1220" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://www.amicited.com/"><strong>Explore AmICited</strong></a>
  ·
  <a href="https://www.amicited.com/features/">AI visibility features</a>
  ·
  <a href="https://www.amicited.com/blog/">AI search insights</a>
</p>

AmICited CLI is the open-source, text-only watermark toolkit from
[AmICited](https://www.amicited.com/), the AI-search visibility platform by
[FlowHunt](https://www.flowhunt.io/). It helps content teams and AI agents find
deterministic artifacts, produce reviewable rewrites, preserve important spans,
and record exactly what changed.

Use it to improve the technical hygiene and human review of AI-assisted content
before it enters your publishing workflow. Removing hidden characters or
rewriting text can reduce specific detectable artifacts, but it does **not**
guarantee evasion of Google or another proprietary system, human authorship, or
higher search rankings. Strong search performance still depends on useful,
original, accurate, and authoritative content.

> **Want to know whether AI search cites your brand?**
> [Run your visibility check with AmICited →](https://www.amicited.com/)

## What it does

- **Inspects locally by default** for hidden Unicode, bidi controls, Unicode
  tags, exotic spaces, confusables, normalization differences, and suspicious
  whitespace.
- **Removes deterministic artifacts safely** while preserving the original,
  line endings, Markdown structure, and a complete change record.
- **Creates protected rewrites** through an API model, Codex CLI, or Claude CLI
  while protecting citations, URLs, quotations, numbers, frontmatter, and code.
- **Verifies before and after** using detector-specific statuses instead of a
  manufactured global confidence score.
- **Works for people and agents** through versioned JSON, a Python SDK, and the
  bundled `amicited-watermarks` skill.

## Install

Install the `amicited` CLI in an isolated environment with
[`uv`](https://docs.astral.sh/uv/guides/tools/):

```bash
uv tool install amicited
amicited watermark capabilities
```

Run it once without a persistent installation:

```bash
uvx amicited watermark capabilities
```

Upgrade later with `uv tool upgrade amicited`. AmICited requires Python 3.11 or
newer; uv can provision a compatible interpreter automatically.

## Quick start

```bash
# Inspect without changing the source
amicited watermark inspect article.md > article-inspection.json

# Produce article_dewatermarked.md and a structured report
amicited watermark rewrite article.md > article-rewrite-report.json

# Use an existing authenticated Codex session for semantic rewriting
amicited watermark rewrite article.md --provider codex > article-rewrite-report.json

# Verify the transformed file against supported deterministic signals
amicited watermark verify article_dewatermarked.md
```

## Agent skill

Install the bundled skill globally without cloning this repository:

```bash
amicited watermark skills
```

Choose Codex or Claude when prompted, or select one directly:

```bash
amicited watermark skills --provider codex
amicited watermark skills --provider claude
```

Codex installs globally at `~/.agents/skills/amicited-watermarks`; Claude Code
installs globally at `~/.claude/skills/amicited-watermarks`. Running the command
again is safe when the bundled and installed copies match. If an existing copy
differs, AmICited refuses to replace it. Use `--force` to preserve the old copy
as a timestamped backup and install the bundled version.

The
[`amicited-watermarks`](https://github.com/yasha-dev1/amicited-cli/tree/main/skills/amicited-watermarks)
skill teaches agents to use file-first input, inspect before rewriting, preserve
the source, request confirmation before external processing, and interpret
verification without overstating the result. Invoke it as
`$amicited-watermarks` in Codex or `/amicited-watermarks` in Claude Code.

## Watermarking and AI visibility

This repository owns AmICited's open-source watermarking layer: preparing and
auditing text before publication. The [AmICited platform](https://www.amicited.com/)
owns the measurement loop after publication—tracking brand mentions, citations,
competitor visibility, and source performance across leading AI search engines.
Together they support a practical workflow: publish cleaner, reviewed content,
then measure whether AI systems discover and cite it.

## CLI

Read text from standard input with `-`, or pass a UTF-8 file path:

```bash
printf 'hello\u200bworld\n' | amicited watermark inspect -
amicited watermark verify article.txt
amicited watermark rewrite article.txt
amicited watermark rewrite article.txt --normalization nfc
amicited watermark rewrite article.txt --map-confusables --strip-semantic-format
amicited watermark capabilities
```

The semantic execution provider is selected with `--provider`. `api` is the
default and uses a LangChain-supported model:

```bash
export OPENAI_API_KEY="..."
amicited watermark rewrite article.txt --provider api --model openai:gpt-5-mini

export ANTHROPIC_API_KEY="..."
amicited watermark rewrite article.txt --provider api --model anthropic:claude-haiku-4-5

export GOOGLE_API_KEY="..."
amicited watermark rewrite article.txt --provider api --model google_genai:gemini-2.5-flash
```

Alternatively, use an existing authenticated Codex or Claude Code CLI session.
The CLI model is optional; omit it to use that tool's configured default:

```bash
amicited watermark rewrite article.txt --provider codex
amicited watermark rewrite article.txt --provider codex --model MODEL

amicited watermark rewrite article.txt --provider claude
amicited watermark rewrite article.txt --provider claude --model sonnet
```

Semantic rewriting is paragraph-oriented. AmICited preserves blank-line
separators, splits an overlong paragraph at a preferred sentence boundary or a
hard word limit, rewrites the resulting passages concurrently, and reassembles
them in source order. Defaults are 180 words per request and four concurrent
requests. DIPPER-style lexical and order diversity targets are included in every
provider prompt and can be configured explicitly:

```bash
amicited watermark rewrite article.txt --provider codex \
  --max-chunk-words 180 --max-concurrency 4 \
  --lexical-diversity 60 --order-diversity 40
```

These diversity values guide a general model through instructions; they are not
the learned control tokens of the original DIPPER model. `--temperature` sets
API-provider sampling only. Codex and Claude use their selected CLI model's
generation settings.

Codex and Claude run non-interactively and receive each bounded protected
passage directly through standard input. Codex uses an ephemeral `read-only`
sandbox and a temporary final-response file. Claude uses safe mode, no session
persistence, and no built-in tools. No original source path is exposed, and the
source remains unchanged.

Codex and Claude activity is streamed live to standard error by default, while
the final AmICited JSON report is written to standard output. This keeps report
redirection machine-readable without hiding provider progress:

```bash
amicited watermark rewrite article.txt --provider codex > report.json
# Writes article_dewatermarked.txt and records it in report.json.
```

Transformation reports exclude source text, transformed text, diff bodies, and
finding context by default. The report contains `"content_included": false`,
checksums, output paths, statuses, and diagnostics without copying a private
article into JSON. Use `--include-content` only when a trusted consumer needs
the text embedded in the report:

```bash
amicited watermark rewrite article.txt --include-content > report-with-text.json
```

Provider output can include the submitted prompt. Use `--no-stream` when the
terminal output may be recorded or when silent automation is required.

File transformations write a sibling output automatically and preserve the
source: `article.md` becomes `article_dewatermarked.md`, and `article.txt`
becomes `article_dewatermarked.txt`. Choose another destination with `-o` or
`--output`. Existing output files are refused unless `--overwrite` is explicit:

```bash
amicited watermark rewrite article.md --provider codex -o revised.md
amicited watermark rewrite article.md --provider codex --overwrite
```

Standard-input transformations remain in memory unless `--output` is supplied,
because stdin has no source filename from which to derive a sibling path.

Use `--cli-timeout SECONDS` to bound either CLI. A missing executable fails
before the source file is read. Authentication failures, exhausted usage,
timeouts, invalid responses, empty responses, and general CLI failures use
stable error categories without copying provider output into the report.

An unqualified model can be paired with `--model-provider`. A custom
OpenAI-compatible endpoint can be selected with `--base-url`. The CLI validates
known provider credentials before reading a file or initializing a request and
returns exit code `4` for configuration or model-processing failures. API keys
are read from the provider's environment variable and never included in reports.

Implemented commands emit versioned JSON. `rewrite` and `remove` transform an
in-memory copy, record every deterministic change, run verification before and
after the transformation, and never overwrite the source file. Written-output
metadata includes the destination, UTF-8 byte and character counts, and SHA-256
checksum.

## Python SDK

The SDK never guesses whether a string is text or a path:

```python
from amicited import watermark

report = watermark.rewrite(watermark.WatermarkInput.text("hello\u200bworld"))
print(report.transformed_text)
print(report.to_json())
# Explicit opt-in when serialized JSON must contain text and diff bodies:
print(report.to_json(include_content=True))

semantic_report = watermark.rewrite(
    watermark.WatermarkInput.text("Text to rewrite."),
    model="openai:gpt-5-mini",
    max_chunk_words=180,
    max_concurrency=4,
    lexical_diversity=60,
    order_diversity=40,
)

codex_report = watermark.rewrite(
    watermark.WatermarkInput.text("Text to rewrite."),
    provider=watermark.SemanticProvider.CODEX,
    progress_callback=lambda text: print(text, end=""),
)
```

Python report objects retain `transformed_text` in memory. Their `to_dict()` and
`to_json()` methods redact content by default. Protected-span failures expose
content-free diagnostics such as expected/found counts, missing, duplicate or
unexpected placeholder IDs, the first mismatch, reordering, and malformed-token
counts. A failed rewrite never creates the adjacent output candidate.

The SDK does not stream unless `progress_callback` is supplied.

`watermark.Watermark` accepts an ordered sequence of `TextWatermarkLayer`
subclasses. Every layer implements `inspect`, `verify`, `rewrite`, and
`capability`. Inspection and verification run all layers in order. Rewrite and
remove feed each layer's output into the next layer and return the individual
layer results as well as the aggregate report.

The default order is:

1. `HiddenUnicodeLayer`
2. `BidiControlLayer`
3. `UnicodeTagLayer`
4. `ExoticSpaceLayer`
5. `ConfusableLayer`
6. `UnicodeNormalizationLayer`
7. `WhitespacePatternLayer`

When an API `model` is explicitly supplied or the `codex`/`claude` provider is
selected, an eighth `SemanticRewriteLayer` runs after the deterministic layers.
Its three backends implement the same execution interface; the API backend uses
LangChain's provider-neutral `init_chat_model`. The layer protects the complete
document, partitions it into paragraph-level passages bounded by the word limit,
and invokes up to `max_concurrency` provider requests in parallel.
Citations, URLs, quotations, numbers, frontmatter, and code are immutable
placeholders. Protected-only passages are not transmitted. Restoration succeeds
only if every placeholder is returned exactly once and in order. A provider
error or protected-span violation preserves the current text and produces a
failed transformation.

Context-sensitive joiners, variation selectors, valid emoji tag sequences,
and balanced bidi controls are reported but preserved. Exotic spaces are mapped
one-for-one; whitespace is never globally collapsed. Confusable mapping,
semantic-format stripping, and NFC/NFKC normalization require explicit options.
Potentially lossy changes remain visible in the structured change list.

Semantic rewriting is non-deterministic and potentially lossy. Its verification
result is always `unverifiable`: paraphrasing is not a statistical-watermark
detector, does not prove removal, and does not establish human authorship. The
selected model and provider, external-processing flag, protected-span status,
meaning risk, chunk count, word/concurrency limits, diversity targets, changes,
and limitations are present in the structured report.

## Contributors

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/yasha-dev1">
        <img src="https://avatars.githubusercontent.com/u/58387199?v=4" width="96" alt="Yasha Boroumand"><br>
        <sub><strong>Yasha Boroumand</strong></sub>
      </a><br>
      <sub>Creator and maintainer</sub>
    </td>
  </tr>
</table>

Community contributions are welcome. See everyone who has helped on the
[GitHub contributors page](https://github.com/yasha-dev1/amicited-cli/graphs/contributors).

## Development

```bash
uv sync
uv run pytest
uv run amicited --help
uv build
```

## Release

Releases are published to PyPI through GitHub Actions and PyPI Trusted
Publishing. Set the version in `pyproject.toml`, commit it, then push a matching
tag such as `v0.1.0`. The release workflow rejects tags that do not exactly
match the package version, runs the full quality suite, builds from the source
distribution, and publishes only after those checks pass.
