"""Docker-hardened sandbox backend for code execution (ROADMAP M3 ①).

Replaces the bare `SubprocessInterpreter` for execute_code when enabled.
Hardening: no network, read-only rootfs, tmpfs /tmp, memory/cpu/pid limits,
auto-remove container, per-exec timeout enforced client-side.

Opt-in via env: CODE_EXEC_BACKEND=docker
Falls back to SubprocessInterpreter when docker is unavailable, so behavior
is never degraded on hosts without docker.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger

from .subprocess_interpreter import SubprocessInterpreter, maybe_wrap_last_expr

DEFAULT_IMAGE = "python:3.12-slim"
_CONTAINER_TMPFS = "/tmp:rw,noexec,nosuid,size=64m"


def docker_available(image: str = DEFAULT_IMAGE) -> bool:
    """True if docker CLI + daemon are usable and the image is pullable/present."""
    if not shutil.which("docker"):
        return False
    try:
        inspect = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True, timeout=10,
        )
        if inspect.returncode == 0:
            return True
        pull = subprocess.run(
            ["docker", "pull", "--quiet", image],
            capture_output=True, timeout=300,
        )
        return pull.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class DockerSandboxInterpreter:
    """Execute Python code inside a hardened docker container.

    Same `run(code) -> str` contract as SubprocessInterpreter so the
    execute_code tool can swap backends transparently.
    """

    def __init__(
        self,
        print_stdout: bool = False,
        print_stderr: bool = False,
        execution_timeout: int = 300,
        image: str = DEFAULT_IMAGE,
        memory: str = "256m",
        cpus: str = "0.5",
        pids_limit: int = 64,
    ) -> None:
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr
        self.execution_timeout = execution_timeout
        self.image = image
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit

    def _docker_cmd(self, code_file: Path) -> list[str]:
        return [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            "--tmpfs", _CONTAINER_TMPFS,
            "--mount", f"type=bind,src={code_file},dst=/work/code.py,ro",
            "--memory", self.memory,
            "--cpus", self.cpus,
            "--pids-limit", str(self.pids_limit),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            self.image,
            "python", "/work/code.py",
        ]

    def run(self, code: str) -> str:
        temp_file: Optional[Path] = None
        try:
            try:
                code = maybe_wrap_last_expr(code)
            except Exception as e:
                logger.warning(f"Failed to parse Python code: {e}")
            fd, tmp = tempfile.mkstemp(suffix=".py", prefix="docker_exec_")
            temp_file = Path(tmp)
            temp_file.write_text(code, encoding="utf-8")
            try:
                import os
                os.close(fd)
            except OSError:
                pass
            return self._exec_in_container(temp_file)
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to clean up temporary file: {e}")

    def _exec_in_container(self, code_file: Path) -> str:
        cmd = self._docker_cmd(code_file)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
            try:
                stdout, stderr = proc.communicate(timeout=self.execution_timeout)
                return_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                return_code = proc.returncode
                stderr = f"{stderr}\nProcess timed out after {self.execution_timeout} seconds."
        except OSError as e:
            return f"Docker sandbox unavailable: {e}"

        if self.print_stdout and stdout:
            print("======stdout======")
            print(stdout)
            print("==================")
        if self.print_stderr and stderr:
            print("======stderr======")
            print(stderr)
            print("==================")

        exec_result = ""
        if stdout:
            exec_result += stdout
        if stderr:
            exec_result += f"(stderr: {stderr})"
        if return_code != 0:
            error_msg = f"(Execution failed, return code {return_code})"
            if not stderr:
                exec_result += error_msg
            elif error_msg not in stderr:
                exec_result += error_msg
        return exec_result


def select_interpreter(
    print_stdout: bool = False,
    print_stderr: bool = False,
    execution_timeout: int = 300,
    backend: str = "subprocess",
) -> object:
    """Pick subprocess or docker sandbox; docker falls back on unavailability."""
    if backend == "docker":
        if docker_available():
            return DockerSandboxInterpreter(
                print_stdout=print_stdout,
                print_stderr=print_stderr,
                execution_timeout=execution_timeout,
            )
        logger.warning("CODE_EXEC_BACKEND=docker but docker unavailable; "
                       "falling back to SubprocessInterpreter")
    return SubprocessInterpreter(
        print_stdout=print_stdout,
        print_stderr=print_stderr,
        execution_timeout=execution_timeout,
    )
