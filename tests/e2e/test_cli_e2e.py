from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

CLI = Path(sys.executable).with_name("amicited")


def run_cli(
    *arguments: str,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *arguments],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def parse_report(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return json.loads(result.stdout)


def test_console_script_exists_and_exposes_the_watermark_namespace() -> None:
    assert CLI.is_file()

    result = run_cli("--help")

    assert result.returncode == 0
    assert "watermark" in result.stdout


@pytest.mark.parametrize(
    ("provider", "relative_destination"),
    [
        ("codex", ".agents/skills/amicited-watermarks"),
        ("claude", ".claude/skills/amicited-watermarks"),
    ],
)
def test_skill_installs_globally_for_each_provider_end_to_end(
    tmp_path: Path,
    provider: str,
    relative_destination: str,
) -> None:
    test_home = tmp_path / "home"
    environment = {**os.environ, "HOME": str(test_home)}

    report = parse_report(
        run_cli(
            "watermark",
            "skills",
            "--provider",
            provider,
            env=environment,
        )
    )

    destination = test_home / relative_destination
    assert report["schema_version"] == "1.0"
    assert report["operation"] == "skills"
    assert report["provider"] == provider
    assert report["scope"] == "global"
    assert report["status"] == "installed"
    assert report["destination"] == str(destination)
    assert (destination / "SKILL.md").is_file()


def test_skill_provider_can_be_selected_interactively_end_to_end(
    tmp_path: Path,
) -> None:
    test_home = tmp_path / "home"
    environment = {**os.environ, "HOME": str(test_home)}

    result = run_cli(
        "watermark",
        "skills",
        input_text="codex\n",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["provider"] == "codex"
    assert "Codex or Claude" in result.stderr
    assert (
        test_home / ".agents" / "skills" / "amicited-watermarks" / "SKILL.md"
    ).is_file()


def test_skill_cli_refuses_changed_content_then_force_backs_it_up_end_to_end(
    tmp_path: Path,
) -> None:
    test_home = tmp_path / "home"
    environment = {**os.environ, "HOME": str(test_home)}
    arguments = ("watermark", "skills", "--provider", "claude")
    parse_report(run_cli(*arguments, env=environment))
    destination = test_home / ".claude" / "skills" / "amicited-watermarks" / "SKILL.md"
    destination.write_text("local customization", encoding="utf-8")

    refused = run_cli(*arguments, env=environment)

    assert refused.returncode == 4
    assert "--force" in refused.stderr
    assert destination.read_text(encoding="utf-8") == "local customization"

    updated = parse_report(run_cli(*arguments, "--force", env=environment))

    assert updated["status"] == "updated"
    backup = Path(updated["backup_path"])
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "local customization"
    assert destination.read_text(encoding="utf-8").startswith("---\n")


def test_stdin_inspect_verify_and_rewrite_work_end_to_end() -> None:
    original = "éA\u200bB\u202eC\u00a0D\U000e0065"

    inspection = parse_report(run_cli("watermark", "inspect", "-", input_text=original))
    verification = parse_report(
        run_cli("watermark", "verify", "-", input_text=original)
    )
    rewrite = parse_report(
        run_cli(
            "watermark",
            "rewrite",
            "-",
            "--include-content",
            input_text=original,
        )
    )

    assert inspection["operation"] == "inspect"
    assert [result["layer_id"] for result in inspection["results"]] == [
        "hidden_unicode",
        "bidi_controls",
        "unicode_tags",
        "exotic_spaces",
        "confusables",
        "unicode_normalization",
        "whitespace_patterns",
    ]
    assert {finding["code_point"] for finding in inspection["findings"]} == {
        "U+200B",
        "U+202E",
        "U+00A0",
        "U+E0065",
    }
    zero_width = next(
        finding
        for finding in inspection["findings"]
        if finding["code_point"] == "U+200B"
    )
    assert zero_width["position"] == {"byte_offset": 3, "code_point_index": 2}
    assert verification["status"] == "detected"
    assert rewrite["transformed_text"] == "éABC D"
    assert rewrite["changed"] is True
    assert rewrite["before_verification"]["status"] == "detected"
    assert rewrite["after_verification"]["status"] == "not_detected"
    assert len(rewrite["changes"]) == 4


@pytest.mark.parametrize("operation", ("rewrite", "remove"))
def test_file_transformation_preserves_the_source_end_to_end(
    tmp_path: Path, operation: str
) -> None:
    source = tmp_path / "article.md"
    original = b"---\r\ntitle: Test\r\n---\r\na\xe2\x80\x8bb\xc2\xa0c\r\n"
    source.write_bytes(original)

    report = parse_report(
        run_cli(
            "watermark",
            operation,
            str(source),
            "--include-content",
        )
    )

    destination = tmp_path / "article_dewatermarked.md"
    assert report["operation"] == operation
    assert report["transformed_text"] == "---\r\ntitle: Test\r\n---\r\nab c\r\n"
    assert report["input"]["path"] == str(source)
    assert report["input"]["byte_count"] == len(original)
    assert report["output"]["path"] == str(destination)
    assert report["output"]["byte_count"] == len(
        report["transformed_text"].encode("utf-8")
    )
    assert source.read_bytes() == original
    assert destination.read_bytes() == report["transformed_text"].encode("utf-8")
    assert sorted(tmp_path.iterdir()) == sorted((source, destination))


def test_rewrite_supports_explicit_short_output_path_end_to_end(
    tmp_path: Path,
) -> None:
    source = tmp_path / "article.txt"
    destination = tmp_path / "rewritten.md"
    source.write_text("hello\u200bworld", encoding="utf-8")

    report = parse_report(
        run_cli(
            "watermark",
            "rewrite",
            str(source),
            "-o",
            str(destination),
        )
    )

    assert source.read_text(encoding="utf-8") == "hello\u200bworld"
    assert destination.read_text(encoding="utf-8") == "helloworld"
    assert report["output"]["path"] == str(destination)
    assert report["output"]["sha256"]


def test_rewrite_refuses_overwrite_unless_explicit_end_to_end(
    tmp_path: Path,
) -> None:
    source = tmp_path / "article.txt"
    destination = tmp_path / "article_dewatermarked.txt"
    source.write_text("hello\u200bworld", encoding="utf-8")
    destination.write_text("keep me", encoding="utf-8")

    refused = run_cli("watermark", "rewrite", str(source))

    assert refused.returncode == 2
    assert refused.stdout == ""
    assert "already exists" in refused.stderr
    assert "--overwrite" in refused.stderr
    assert destination.read_text(encoding="utf-8") == "keep me"

    replaced = parse_report(run_cli("watermark", "rewrite", str(source), "--overwrite"))

    assert destination.read_text(encoding="utf-8") == "helloworld"
    assert replaced["output"]["path"] == str(destination)


def test_stdin_rewrite_only_writes_when_output_is_explicit(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "stdin-result.txt"

    in_memory = parse_report(
        run_cli("watermark", "rewrite", "-", input_text="a\u200bb")
    )
    written = parse_report(
        run_cli(
            "watermark",
            "rewrite",
            "-",
            "--output",
            str(destination),
            input_text="a\u200bb",
        )
    )

    assert in_memory["output"] is None
    assert destination.read_text(encoding="utf-8") == "ab"
    assert written["output"]["path"] == str(destination)


def test_clean_and_empty_inputs_return_not_detected_end_to_end() -> None:
    for text in ("", "plain ASCII\n"):
        report = parse_report(run_cli("watermark", "verify", "-", input_text=text))
        assert report["status"] == "not_detected"
        assert all(result["status"] == "not_detected" for result in report["results"])


def test_capabilities_are_local_deterministic_and_text_only_end_to_end() -> None:
    report = parse_report(run_cli("watermark", "capabilities"))

    assert [item["id"] for item in report["capabilities"]] == [
        "hidden_unicode",
        "bidi_controls",
        "unicode_tags",
        "exotic_spaces",
        "confusables",
        "unicode_normalization",
        "whitespace_patterns",
        "semantic_rewrite",
    ]
    assert all(item["modalities"] == ["text"] for item in report["capabilities"])
    assert all(item["deterministic"] is True for item in report["capabilities"][:-1])
    assert all(
        item["network_required"] is False for item in report["capabilities"][:-1]
    )
    assert report["capabilities"][-1]["deterministic"] is False
    assert report["capabilities"][-1]["network_required"] is True
    assert report["capabilities"][-1]["execution_providers"] == [
        "api",
        "codex",
        "claude",
    ]


def test_invalid_utf8_file_returns_a_stable_input_error(tmp_path: Path) -> None:
    source = tmp_path / "invalid.txt"
    source.write_bytes(b"valid prefix\xffprivate suffix")

    result = run_cli("watermark", "inspect", str(source))

    assert result.returncode == 2
    assert result.stdout == ""
    assert "valid UTF-8" in result.stderr
    assert "private suffix" not in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_file_returns_a_stable_input_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"

    result = run_cli("watermark", "verify", str(missing))

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Unable to read input file" in result.stderr
    assert "Traceback" not in result.stderr


def test_explicit_deterministic_cleanup_options_work_end_to_end() -> None:
    original = "a\u200cb pаypal Ａ\u00a0B"

    report = parse_report(
        run_cli(
            "watermark",
            "rewrite",
            "-",
            "--strip-semantic-format",
            "--map-confusables",
            "--no-normalize-spaces",
            "--normalization",
            "nfkc",
            "--include-content",
            input_text=original,
        )
    )

    assert report["transformed_text"] == "ab paypal A B"
    assert report["after_verification"]["status"] == "not_detected"


def test_semantic_rewrite_without_provider_key_fails_safely_end_to_end() -> None:
    environment = dict(os.environ)
    environment.pop("OPENAI_API_KEY", None)

    result = run_cli(
        "watermark",
        "rewrite",
        "-",
        "--model",
        "openai:test-model",
        input_text="private input must not appear in the error",
        env=environment,
    )

    assert result.returncode == 4
    assert result.stdout == ""
    assert "OPENAI_API_KEY" in result.stderr
    assert "private input" not in result.stderr
    assert "Traceback" not in result.stderr


def test_ambiguous_semantic_model_fails_with_stable_exit_end_to_end() -> None:
    result = run_cli(
        "watermark",
        "rewrite",
        "-",
        "--model",
        "custom-model",
        input_text="private input",
    )

    assert result.returncode == 4
    assert result.stdout == ""
    assert "ambiguous" in result.stderr
    assert "private input" not in result.stderr
    assert "Traceback" not in result.stderr


def test_semantic_rewrite_uses_selected_model_through_langchain_end_to_end() -> None:
    requests: list[dict[str, Any]] = []

    class ModelHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(length))
            requests.append(payload)
            prompt = payload["messages"][-1]["content"]
            protected_text = prompt.split("<TEXT>\n", 1)[1].rsplit("\n</TEXT>", 1)[0]
            rewritten = protected_text.replace(
                "The original sentence is predictable.",
                "A fresh structure communicates the same point.",
            )
            response = json.dumps(
                {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "created": 1,
                    "model": payload["model"],
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": rewritten},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 10,
                        "total_tokens": 20,
                    },
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        environment = dict(os.environ)
        environment["OPENAI_API_KEY"] = "local-test-key"
        report = parse_report(
            run_cli(
                "watermark",
                "rewrite",
                "-",
                "--model",
                "openai:test-model",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1",
                "--include-content",
                input_text="The original sentence is predictable.",
                env=environment,
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert report["transformed_text"] == (
        "A fresh structure communicates the same point."
    )
    assert report["verification_status"] == "unverifiable"
    assert report["results"][-1]["layer_id"] == "semantic_rewrite"
    assert report["results"][-1]["model"] == "openai:test-model"
    assert report["results"][-1]["execution_provider"] == "api"
    assert requests[0]["model"] == "test-model"


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_missing_model_cli_fails_with_stable_exit_end_to_end(provider: str) -> None:
    environment = dict(os.environ)
    environment["PATH"] = "/usr/bin:/bin"

    result = run_cli(
        "watermark",
        "rewrite",
        "-",
        "--provider",
        provider,
        input_text="private input",
        env=environment,
    )

    assert result.returncode == 4
    assert result.stdout == ""
    assert f"'{provider}'" in result.stderr
    assert "not installed" in result.stderr
    assert "private input" not in result.stderr
    assert "Traceback" not in result.stderr


def _write_fake_model_cli(
    directory: Path, provider: str, *, failure: str | None
) -> None:
    executable = directory / provider
    if failure is None:
        provider_body = (
            "output = text.replace('Original sentence.', "
            f"'{provider.title()} rewrite.')\n"
            "if name == 'codex':\n"
            "    sys.stderr.write('Codex is rewriting...\\n')\n"
            "    sys.stderr.flush()\n"
            "    destination = pathlib.Path(args[args.index('--output-last-message') + 1])\n"
            "    destination.write_text(output, encoding='utf-8')\n"
            "else:\n"
            "    if args[args.index('--output-format') + 1] == 'stream-json':\n"
            "        sys.stdout.write(json.dumps({\n"
            "            'type': 'stream_event',\n"
            "            'event': {'type': 'content_block_delta', 'delta': {\n"
            "                'type': 'text_delta', 'text': 'Claude is rewriting...'\n"
            "            }}\n"
            "        }) + '\\n')\n"
            "        sys.stdout.flush()\n"
            "    sys.stdout.write(json.dumps({\n"
            "        'type': 'result', 'is_error': False, "
            "'result': output\n"
            "    }) + '\\n')\n"
            "    sys.stdout.flush()\n"
        )
    else:
        provider_body = f"sys.stderr.write({failure!r})\nsys.exit(1)\n"
    executable.write_text(
        "#!/usr/bin/python3\n"
        "import json\n"
        "import pathlib\n"
        "import sys\n"
        "name = pathlib.Path(sys.argv[0]).name\n"
        "args = sys.argv[1:]\n"
        "prompt = sys.stdin.read()\n"
        "start = prompt.index('<TEXT>\\n') + len('<TEXT>\\n')\n"
        "text = prompt[start:prompt.index('\\n</TEXT>', start)]\n"
        "if 'amicited-protected-input.md' in prompt:\n"
        "    raise SystemExit('unexpected file handoff')\n"
        f"{provider_body}",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def test_long_markdown_placeholder_failure_is_actionable_private_and_fail_closed(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text(
        "#!/usr/bin/python3\n"
        "import pathlib\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "prompt = sys.stdin.read()\n"
        "destination = pathlib.Path(args[args.index('--output-last-message') + 1])\n"
        "destination.write_text("
        "'Incomplete rewrite __AMICITED_PROTECTED_0000__', encoding='utf-8')\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"
    sentinel = "PRIVATE-SENTINEL-ARTICLE-CONTENT"
    source = tmp_path / "large-article.md"
    original = "---\ntitle: Private draft\n---\n\n" + "\n\n".join(
        (
            f"## Section\n\n{sentinel} paragraph with protected value {index}. "
            + "Long-form prose for a realistic article workload. " * 3
        )
        for index in range(100)
    )
    assert 20_000 <= len(original) <= 30_000
    source.write_text(original, encoding="utf-8")

    result = run_cli(
        "watermark",
        "rewrite",
        str(source),
        "--provider",
        "codex",
        "--no-stream",
        env=environment,
    )

    assert result.returncode == 4
    assert result.stderr == ""
    assert sentinel not in result.stdout
    assert len(result.stdout.encode("utf-8")) < 50_000
    report = json.loads(result.stdout)
    semantic = report["results"][-1]
    diagnostics = semantic["protected_span_diagnostics"]
    assert report["transformation_status"] == "failed"
    assert report["changed"] is False
    assert report["content_included"] is False
    assert report["transformed_text"] is None
    assert all(layer["text"] is None for layer in report["results"])
    assert semantic["protected_spans_preserved"] is False
    assert semantic["error_category"] == "protected_span_violation"
    assert diagnostics["expected_count"] >= 100
    assert diagnostics["found_count"] > 1
    assert diagnostics["first_mismatch_index"] == 1
    assert diagnostics["missing_ids"][0] == "0001"
    assert source.read_text(encoding="utf-8") == original
    assert not (tmp_path / "large-article_dewatermarked.md").exists()


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_long_markdown_cli_parallel_passages_preserve_all_placeholders(
    tmp_path: Path, provider: str
) -> None:
    _write_fake_model_cli(tmp_path, provider, failure=None)
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"
    source = tmp_path / "large-success.md"
    original = "\n\n".join(
        (
            f"## Section\n\nOriginal sentence. Protected value {index}. "
            + "Long-form Markdown prose stays outside the command prompt. " * 3
        )
        for index in range(100)
    )
    assert 20_000 <= len(original) <= 30_000
    source.write_text(original, encoding="utf-8")

    result = run_cli(
        "watermark",
        "rewrite",
        str(source),
        "--provider",
        provider,
        "--no-stream",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    destination = tmp_path / "large-success_dewatermarked.md"
    rewritten = destination.read_text(encoding="utf-8")
    assert rewritten.count(f"{provider.title()} rewrite.") == 100
    assert all(f"Protected value {index}." in rewritten for index in range(100))
    assert source.read_text(encoding="utf-8") == original
    assert report["content_included"] is False
    assert report["transformed_text"] is None
    assert report["results"][-1]["protected_spans_preserved"] is True
    assert report["results"][-1]["protected_span_diagnostics"] is None
    assert report["results"][-1]["execution_provider"] == provider
    assert report["results"][-1]["chunk_count"] >= 100
    assert report["results"][-1]["max_chunk_words"] == 180
    assert report["results"][-1]["max_concurrency"] == 4


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_model_cli_success_works_through_real_subprocess_end_to_end(
    tmp_path: Path,
    provider: str,
) -> None:
    _write_fake_model_cli(tmp_path, provider, failure=None)
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"

    result = run_cli(
        "watermark",
        "rewrite",
        "-",
        "--provider",
        provider,
        "--include-content",
        input_text="Original sentence.",
        env=environment,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)

    assert report["transformed_text"] == f"{provider.title()} rewrite."
    assert report["verification_status"] == "unverifiable"
    assert report["results"][-1]["execution_provider"] == provider
    assert report["results"][-1]["external_processing"] is True
    assert f"[{provider}]" in result.stderr
    assert f"{provider.title()} is rewriting..." in result.stderr


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_model_cli_stream_can_be_disabled_end_to_end(
    tmp_path: Path,
    provider: str,
) -> None:
    _write_fake_model_cli(tmp_path, provider, failure=None)
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"

    result = run_cli(
        "watermark",
        "rewrite",
        "-",
        "--provider",
        provider,
        "--no-stream",
        "--include-content",
        input_text="Original sentence.",
        env=environment,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["transformed_text"] == (
        f"{provider.title()} rewrite."
    )
    assert result.stderr == ""


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_model_cli_rewrites_article_from_file_end_to_end(
    tmp_path: Path,
    provider: str,
) -> None:
    _write_fake_model_cli(tmp_path, provider, failure=None)
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"
    source = tmp_path / "article.md"
    destination = tmp_path / "article_dewatermarked.md"
    source.write_text("# Article\n\nOriginal sentence.\n", encoding="utf-8")

    result = run_cli(
        "watermark",
        "rewrite",
        str(source),
        "--provider",
        provider,
        "--no-stream",
        env=environment,
    )

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert source.read_text(encoding="utf-8") == "# Article\n\nOriginal sentence.\n"
    assert destination.read_text(encoding="utf-8") == (
        "# Article\n\n" + f"{provider.title()} rewrite.\n"
    )
    assert report["input"]["kind"] == "file"
    assert report["input"]["path"] == str(source)
    assert report["output"]["path"] == str(destination)


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_model_cli_usage_exhaustion_is_structured_end_to_end(
    tmp_path: Path,
    provider: str,
) -> None:
    usage_message = "You've hit your usage limit; resets later"
    _write_fake_model_cli(tmp_path, provider, failure=usage_message)
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"

    result = run_cli(
        "watermark",
        "rewrite",
        "-",
        "--provider",
        provider,
        input_text="private input",
        env=environment,
    )

    assert result.returncode == 4
    report = json.loads(result.stdout)
    assert report["transformation_status"] == "failed"
    assert report["results"][-1]["error_category"] == "usage_exhausted"
    assert usage_message not in result.stdout
    assert usage_message in result.stderr
