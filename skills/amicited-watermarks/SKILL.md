---
name: amicited-watermarks
description: Inspect, sanitize, verify, and produce reviewable text rewrites with the AmICited Watermark CLI using file-first inputs for articles and other long text. Use when an agent is asked to find hidden Unicode or text watermark signals, remove deterministic text artifacts, rewrite text through an explicitly approved model provider, or interpret an AmICited JSON report. Do not use for media watermarks, AI-authorship classification, undisclosed attribution removal, or claims of universal/provider-specific watermark removal.
---

# AmICited Watermarks

Use the `amicited watermark` CLI as a text-only, evidence-limited workflow. Treat
every semantic rewrite as potentially lossy and every detector verdict as scoped
to the detector that produced it.

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
   article path.

Use concrete file commands such as:

```bash
amicited watermark inspect article.md > article-inspection.json
amicited watermark rewrite article.md > article-rewrite-report.json
amicited watermark verify article_dewatermarked.md > article-verification.json
```

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
   `failed` result.
4. For deterministic sanitation only, omit `--model` and use:

   ```bash
   amicited watermark rewrite article.md > article-rewrite-report.json
   ```

   A file input automatically produces `NAME_dewatermarked.md` or
   `NAME_dewatermarked.txt`. Use `-o CANDIDATE` for a different reviewable
   destination. Treat that separate candidate as the preview; inspect its diff
   before accepting it.
5. Before semantic rewriting, explain that content will leave the deterministic
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
   when terminal output may be retained.
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
  current source and report the structured error category.
