"""Structured LLM calls through the headless Claude Code CLI (uses the logged-in account).

This is the only module that knows how the model is reached. To use the Anthropic API
instead, reimplement complete_json with the same signature.
"""

import json
import subprocess
import tempfile


class LLMError(RuntimeError):
    pass


def complete_json(system, prompt, schema, model=None, effort=None, timeout=1800):
    cmd = [
        "claude", "-p",
        "--tools", "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--system-prompt", system,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
    ]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    # Run outside the project so no project instructions or memory leak into the prompt.
    with tempfile.TemporaryDirectory() as cwd:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    if proc.returncode != 0:
        raise LLMError(f"claude exited {proc.returncode}: {proc.stderr.strip()[-2000:]}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"unparseable CLI output: {proc.stdout[:500]}") from e
    if result.get("is_error") or "structured_output" not in result:
        raise LLMError(f"no structured output: {str(result.get('result'))[:500]}")
    return result["structured_output"], result.get("total_cost_usd", 0.0)
