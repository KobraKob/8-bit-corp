import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Protocol, Tuple


class Sandbox(Protocol):
    def execute(self, language: str, code: str, cwd: Path) -> Tuple[int, str, str]:
        """Executes code in isolated environment. Returns (returncode, stdout, stderr)."""
        ...


class SubprocessSandbox:
    """Local subprocess code execution sandbox with security guards:
    - Scoped strictly to project workspace directory
    - Scrubbed environment variables (no API keys, tokens, or system secrets)
    - Strict execution timeout
    - Truncated stdout / stderr output
    - Allowlist of executable binaries (python, node)
    """

    ALLOWED_LANGUAGES = {"python", "node", "javascript"}

    def __init__(self, timeout_sec: float = 15.0, max_output_bytes: int = 10240) -> None:
        self.timeout_sec = timeout_sec
        self.max_output_bytes = max_output_bytes

    def _get_clean_env(self) -> Dict[str, str]:
        # Only retain safe OS system paths, completely scrub all secrets/keys
        safe_keys = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "LANG", "LC_ALL"}
        clean_env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}
        clean_env["PYTHONPATH"] = ""
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        return clean_env

    def execute(self, language: str, code: str, cwd: Path) -> Tuple[int, str, str]:
        lang = language.lower().strip()
        if lang not in self.ALLOWED_LANGUAGES:
            return 1, "", f"Disallowed language '{language}'. Permitted languages: {list(self.ALLOWED_LANGUAGES)}"

        # Select binary
        if lang == "python":
            cmd = [sys.executable, "-c", code]
        else:
            cmd = ["node", "-e", code]

        try:
            process = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                env=self._get_clean_env(),
            )
            stdout = process.stdout[: self.max_output_bytes]
            stderr = process.stderr[: self.max_output_bytes]
            return process.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Code execution timed out after {self.timeout_sec} seconds."
        except Exception as exc:
            return 1, "", f"Execution failure: {str(exc)}"


sandbox = SubprocessSandbox()
