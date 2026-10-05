"""
Safe code execution sandbox for model-generated Python code.
Executes untrusted code with timeouts and isolation via Docker container if available,
or fallback isolated subprocess execution.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


def _is_docker_available() -> bool:
    """Check if Docker CLI is installed and responsive."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        res = subprocess.run(
            [docker_bin, "info"],
            capture_output=True,
            timeout=3,
            check=False,
        )
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_tests(code: str, tests: str, timeout_s: int = 10) -> dict:
    """Execute code + tests safely inside Docker (or isolated subprocess fallback).

    Args:
        code: Python source code snippet or function definition.
        tests: Python assert statements to verify the code.
        timeout_s: Maximum execution time in seconds.

    Returns:
        {"passed": bool, "error": str | None, "timed_out": bool}
    """
    full_script = f"{code}\n\n{tests}\n"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        script_file = temp_path / "solution.py"

        use_docker = _is_docker_available()

        if not use_docker:
            # Network block guard for fallback mode
            socket_guard = (
                "import socket\n"
                "def _block_net(*args, **kwargs):\n"
                "    raise PermissionError('Network access is disabled in sandbox')\n"
                "socket.socket = _block_net\n\n"
            )
            full_script = socket_guard + full_script

        script_file.write_text(full_script, encoding="utf-8")

        if use_docker:
            docker_bin = shutil.which("docker")
            # Mount directory read-only, disable network, limit memory and CPU
            # Note: converting Windows path for Docker volume mounting if needed
            host_work = str(temp_path.resolve()).replace("\\", "/")
            cmd = [
                docker_bin, "run", "--rm",
                "--network", "none",
                "--memory", "512m",
                "--cpus", "1",
                "-v", f"{host_work}:/work:ro",
                "python:3.11-slim",
                "python", "/work/solution.py"
            ]
        else:
            # Subprocess fallback with isolated environment
            clean_env = os.environ.copy()
            clean_env["PYTHONPATH"] = ""
            clean_env["HTTP_PROXY"] = ""
            clean_env["HTTPS_PROXY"] = ""
            clean_env["http_proxy"] = ""
            clean_env["https_proxy"] = ""

            cmd = [
                sys.executable,
                str(script_file.resolve())
            ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=temp_dir if not use_docker else None,
                env=clean_env if not use_docker else None,
                check=False,
            )

            if proc.returncode == 0:
                return {"passed": True, "error": None, "timed_out": False}
            else:
                err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Process exited with code {proc.returncode}"
                return {"passed": False, "error": err_msg, "timed_out": False}

        except subprocess.TimeoutExpired:
            return {"passed": False, "error": f"Execution timed out after {timeout_s} seconds", "timed_out": True}
        except Exception as ex:  # noqa: BLE001
            return {"passed": False, "error": str(ex), "timed_out": False}
