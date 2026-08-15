---
name: amicited-watermarks
description: Inspect, sanitize, verify, and semantically rewrite articles and other long text with the AmICited Watermark CLI using file-first inputs and an explicitly selected API, Codex, or Claude provider. Use when an agent is asked to find hidden Unicode or text watermark signals, remove deterministic text artifacts, produce a reviewable dewatermarked rewrite, or interpret an AmICited JSON report. For article rewriting, treat deterministic inspection as a preflight and semantic rewriting as the expected outcome unless the user explicitly requests local deterministic cleanup only. Do not use for media watermarks, AI-authorship classification, undisclosed attribution removal, or claims of universal/provider-specific watermark removal.
---

# AmICited Watermarks

Use the `amicited watermark` CLI as a text-only, evidence-limited workflow. Treat
every semantic rewrite as potentially lossy and every detector verdict as scoped
to the detector that produced it. Semantic rewriting is the expected default for
articles and long-form content; deterministic inspection and sanitation are
preflight layers, not a substitute for a provider-backed rewrite.

## Establish capabilities

1. Check that `amicited` is available with `command -v amicited`.
2. If it is absent, tell the user to install it with `uv tool install amicited`.
   Do not install software without permission.
3. Run `amicited watermark capabilities` and read its JSON before selecting an
   operation. Do not infer unsupported functionality from a provider name.

## Use file-first input

1. Put every article or other long text in a UTF-8 `.md` or `.txt` file before
   invoking AmICited. If the agent authored the content, write it directly to a
   file with the agent's file-writing tool. If the user supplied long text in
   chat, create a clearly named working file while preserving their original
   content exactly.
2. Pass only the file path as the positional CLI input. Never embed long text in
   a shell argument, command substitution, heredoc, or inline `echo`/`printf`
   command. Do not pipe long text to `amicited ... -`.
3. Reserve `-` and shell stdin for short diagnostics or explicit user-requested
   pipelines. Prefer file paths even then when later inspection, rewriting, or
   verification will reuse the content.
4. Keep JSON reports in separate files and never confuse a report path with the
   article path. Transformation JSON excludes article and diff bodies by default;
   read the adjacent transformed file when reviewing content. Do not add
   `--include-content` unless the user explicitly needs content duplicated into
   a trusted report destination.

Use concrete file commands such as:

```bash
amicited watermark inspect article.md > article-inspection.json
amicited watermark rewrite article.md --provider codex > article-rewrite-report.json
amicited watermark verify article_dewatermarked.md > article-verification.json
```

Every rewrite above preserves `article.md` and creates
`article_dewatermarked.md` beside it. A `.txt` input likewise creates
`NAME_dewatermarked.txt`. The original `article.md` remains unchanged.

## Select a semantic provider

1. Require an explicit provider for an article rewrite. If the user already
   selected `codex`, `claude`, or `api`, use it. Otherwise, ask the user to
   choose `codex`, `claude`, or `api` before rewriting.
2. When operating inside Codex, recommend `codex`; when operating inside Claude
   Code, recommend `claude`. Still identify that provider and obtain user
   confirmation before sending the file content.
3. For `codex` or `claude`, a model is optional and the authenticated CLI
   default may be used. For `api`, require `--model PROVIDER:MODEL` and its
   environment credential.
4. Never run `amicited watermark rewrite ARTICLE` without an explicit
   `--provider` as the final article rewrite. The CLI default (`api` with no
   model) runs deterministic layers only and does not perform semantic rewriting.
5. Do not treat a no-change deterministic report as completion. Complete the
   confirmed provider-backed rewrite, or clearly report that it was not run
   because the user requested deterministic-only processing, declined external
   processing, or no provider was available.

## Follow the safe workflow

1. Preserve the source. Never use `--overwrite` unless the user explicitly
   approves replacing an existing transformed output. Never target the source
   path with `--output`.
2. Inspect first:

   ```bash
   amicited watermark inspect article.md > article-inspection.json
   ```

3. Read the structured JSON. Report which signal types and layers were tested,
   their findings, and every `unsupported`, `unverifiable`, `not_configured`, or
   `failed` result. Continue to semantic rewriting even when deterministic
   inspection finds nothing; that is a normal outcome.
4. Before semantic rewriting, explain that content will leave the deterministic
   local workflow, identify the selected destination/provider, and obtain user
   confirmation. Then choose exactly one explicitly approved backend:

   ```bash
   amicited watermark rewrite article.md --provider codex > article-rewrite-report.json
   amicited watermark rewrite article.md --provider claude > article-rewrite-report.json
   amicited watermark rewrite article.md --provider api --model PROVIDER:MODEL > article-rewrite-report.json
   ```

   API mode requires the provider credential in the environment. Never request,
   print, log, or place an API key in a command, prompt, or report. Codex and
   Claude progress is on stderr and can echo submitted text; add `--no-stream`
   when terminal output may be retained. For Codex and Claude, AmICited uses an
   isolated temporary file handoff; the agent prompt contains temporary
   filenames rather than the complete article. API mode still transmits content
   directly to the selected remote endpoint.
5. Let the CLI choose its safe adjacent output path by omitting `--output`:
   `article.md` becomes `article_dewatermarked.md` and `article.txt` becomes
   `article_dewatermarked.txt`. The JSON redirection stores the report separately
   and does not redirect the rewritten article. Never pass `--overwrite` for the
   source file.
6. Review the candidate against the source. Confirm that citations, URLs, direct
   quotations, numbers, named entities, Markdown, frontmatter, and code remain
   correct. Report protected-span violations, formatting changes, and possible
   meaning drift. Never infer semantic equivalence from a similarity score.
7. Verify the candidate with its explicit path:

   ```bash
   amicited watermark verify article_dewatermarked.md > article-verification.json
   ```

8. Summarize the transformation separately from verification. Include the
   output path, checksum, executed strategies, changes, warnings, limitations,
   before/after detector states, and any unverified signal classes.

Use deterministic-only rewriting solely when the user explicitly requests a
local cleanup or declines all semantic providers:

```bash
amicited watermark rewrite article.md > article-rewrite-report.json
```

Label this result deterministic-only and do not present it as the requested
semantic rewrite.

## Interpret statuses exactly

- `detected`: a compatible detector ran and crossed its configured threshold.
- `not_detected`: that detector ran and did not cross its threshold. This never
  establishes human authorship.
- `not_configured`: required key, tokenizer, model, threshold, or calibration is
  missing.
- `unsupported`: the detector cannot process this input, modality, or scheme.
- `unverifiable`: no compatible authoritative detector can verify the result.
- `failed`: execution encountered an error. Never rewrite this as
  `not_detected`.

Keep `ai_style_classifier` separate from watermark verification. Never combine
unrelated detector scores into a global confidence score.

## Enforce claim boundaries

- Never call a completed transformation verified unless a compatible detector
  actually returned a detector-specific result.
- Never claim OpenAI, Anthropic, Gemini, or another provider's private watermark
  was removed without a compatible authoritative provider detector.
- Never equate artifact removal, rewriting, translation, or metadata removal.
- Never generate homoglyphs, typos, invisible-character evasion, or provenance
  removal without disclosure and permission.
- Never transmit content merely because a model provider is configured.
- Stop after a failed or protected-span-violating transformation; preserve the
  current source and report the structured error category. For
  `protected_span_violation`, report the content-free expected/found counts,
  first mismatch, missing/duplicate/unexpected IDs, reordering state, and
  malformed-placeholder count. Do not expose the protected values.
