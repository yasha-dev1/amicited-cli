# AmICited

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

## Agent skill

Install the bundled agent skill without cloning the repository:

```bash
amicited watermark skills
```

Choose Codex or Claude when prompted. The same command can be used without a
prompt in automation:

```bash
amicited watermark skills --provider codex
amicited watermark skills --provider claude
```

Codex installs globally at `~/.agents/skills/amicited-watermarks`; Claude Code
installs globally at `~/.claude/skills/amicited-watermarks`. Running the command
again is safe when the bundled and installed copies match. If an existing copy
differs, AmICited refuses to replace it. Use `--force` to update only when
intended; the previous copy is retained in a timestamped sibling backup.

The package includes the
[`amicited-watermarks`](https://github.com/yasha-dev1/amicited-cli/tree/main/skills/amicited-watermarks)
skill. It teaches an agent to inspect before rewriting, preserve the source,
request confirmation before external model processing, verify transformed text,
and interpret detector statuses without overstating the result. It also requires
agents to put articles and other long text in UTF-8 `.md` or `.txt` files and
pass only the file path to the CLI. Restart the agent if a newly created
top-level skills directory is not detected. Invoke the skill as
`$amicited-watermarks` in Codex or `/amicited-watermarks` in Claude Code.

AmICited's open-source command-line interface and Python SDK. The current
implementation is text-only and local by default. Semantic rewriting sends text
to an external model only when a model is explicitly selected.

Version 1 is scoped to the `amicited watermark` namespace and the
`amicited.watermark` SDK module. Its first implementation detects and
deterministically inspects and sanitizes hidden Unicode characters,
bidirectional controls, Unicode tags, exotic spaces, potential confusables,
normalization differences, and suspicious whitespace patterns. These checks do
not detect statistical or provider-private watermarks and do not establish
whether text is human-authored.

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

Codex runs non-interactively in an empty temporary directory with a read-only
sandbox and an ephemeral session. Claude runs in safe mode with tools disabled
and session persistence disabled. Input is sent over standard input rather than
command-line arguments. Temporary output is removed after the operation.

Codex and Claude activity is streamed live to standard error by default, while
the final AmICited JSON report is written to standard output. This keeps report
redirection machine-readable without hiding provider progress:

```bash
amicited watermark rewrite article.txt --provider codex > report.json
# Writes article_dewatermarked.txt and records it in report.json.
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

semantic_report = watermark.rewrite(
    watermark.WatermarkInput.text("Text to rewrite."),
    model="openai:gpt-5-mini",
)

codex_report = watermark.rewrite(
    watermark.WatermarkInput.text("Text to rewrite."),
    provider=watermark.SemanticProvider.CODEX,
    progress_callback=lambda text: print(text, end=""),
)
```

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

When `model` is explicitly supplied to `rewrite` or `remove`, an eighth
`SemanticRewriteLayer` runs after the deterministic layers. Its `api`, `codex`,
and `claude` backends implement the same execution interface; the API backend
uses LangChain's provider-neutral `init_chat_model`. Citations, URLs, quotations,
numbers, frontmatter, and code are replaced with immutable placeholders before
the request and restored only if the model returns every placeholder exactly
once and in order. A provider error or protected-span violation preserves the
current text and produces a failed transformation.

Context-sensitive joiners, variation selectors, valid emoji tag sequences,
and balanced bidi controls are reported but preserved. Exotic spaces are mapped
one-for-one; whitespace is never globally collapsed. Confusable mapping,
semantic-format stripping, and NFC/NFKC normalization require explicit options.
Potentially lossy changes remain visible in the structured change list.

Semantic rewriting is non-deterministic and potentially lossy. Its verification
result is always `unverifiable`: paraphrasing is not a statistical-watermark
detector, does not prove removal, and does not establish human authorship. The
selected model and provider, external-processing flag, protected-span status,
meaning risk, changes, and limitations are present in the structured report.

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
