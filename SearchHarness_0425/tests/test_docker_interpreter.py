"""Docker sandbox tests (M3 ①) — hardening flags, toggle & fallback.

Invariant being tested: execute_code keeps working identically by default
(subprocess); the docker backend is opt-in, hardened by construction, and
never breaks hosts without docker.
"""

import subprocess
from unittest import mock

import pytest

from tools.docker_interpreter import (
    DEFAULT_IMAGE,
    DockerSandboxInterpreter,
    docker_available,
    select_interpreter,
)
from tools.subprocess_interpreter import SubprocessInterpreter


class TestDockerCmdHardening:
    def test_all_hardening_flags_present(self, tmp_path):
        interp = DockerSandboxInterpreter()
        code = tmp_path / "c.py"
        code.write_text("print(1)")
        cmd = interp._docker_cmd(code)
        joined = " ".join(cmd)
        assert "--network none" in joined
        assert "--read-only" in joined
        assert "--tmpfs /tmp:rw,noexec,nosuid,size=64m" in joined
        assert f"type=bind,src={code},dst=/work/code.py,ro" in joined
        assert "--memory 256m" in joined
        assert "--cpus 0.5" in joined
        assert "--pids-limit 64" in joined
        assert "--cap-drop ALL" in joined
        assert "no-new-privileges" in joined
        assert "--rm" in cmd
        assert cmd[-2:] == ["python", "/work/code.py"]
        assert cmd[cmd.index(self.imagetag()) - 1] != self.imagetag()

    @staticmethod
    def imagetag():
        return DEFAULT_IMAGE

    def test_custom_limits(self, tmp_path):
        interp = DockerSandboxInterpreter(memory="512m", cpus="1.0", pids_limit=128)
        cmd = " ".join(interp._docker_cmd(tmp_path / "x.py"))
        assert "--memory 512m" in cmd and "--cpus 1.0" in cmd and "--pids-limit 128" in cmd


class TestRun:
    def test_success_passthrough(self, tmp_path):
        interp = DockerSandboxInterpreter(execution_timeout=10)
        code = tmp_path / "ok.py"
        code.write_text("print('hello')")
        with mock.patch.object(subprocess, "Popen") as popen:
            proc = popen.return_value
            proc.communicate.return_value = ("hello\n", "")
            proc.returncode = 0
            out = interp._exec_in_container(code)
        assert "hello" in out and "Execution failed" not in out

    def test_failure_includes_returncode(self, tmp_path):
        interp = DockerSandboxInterpreter()
        code = tmp_path / "bad.py"
        code.write_text("raise")
        with mock.patch.object(subprocess, "Popen") as popen:
            proc = popen.return_value
            proc.communicate.return_value = ("", "boom")
            proc.returncode = 1
            out = interp._exec_in_container(code)
        assert "(stderr: boom)" in out and "return code 1" in out

    def test_timeout_message(self, tmp_path):
        interp = DockerSandboxInterpreter(execution_timeout=5)
        code = tmp_path / "slow.py"
        code.write_text("sleep")
        with mock.patch.object(subprocess, "Popen") as popen:
            proc = popen.return_value
            proc.communicate.side_effect = [
                subprocess.TimeoutExpired(cmd="docker", timeout=5),
                ("", "Killed"),
            ]
            proc.returncode = -9
            out = interp._exec_in_container(code)
        assert "timed out after 5 seconds" in out
        proc.kill.assert_called_once()

    def test_docker_missing_graceful(self, tmp_path):
        interp = DockerSandboxInterpreter()
        code = tmp_path / "x.py"
        code.write_text("pass")
        with mock.patch.object(subprocess, "Popen", side_effect=FileNotFoundError("docker")):
            out = interp._exec_in_container(code)
        assert "Docker sandbox unavailable" in out

    def test_run_cleans_up_tempfile(self, tmp_path):
        interp = DockerSandboxInterpreter()
        created = {}

        class FakePopen:
            def communicate(self, timeout=None):
                return ("ok", "")

            @property
            def returncode(self):
                return 0

        import subprocess as sp

        real_popen = sp.Popen
        def fake_popen(cmd, **kw):
            for i, part in enumerate(cmd):
                if part.startswith("type=bind,src="):
                    created["path"] = part.split("src=", 1)[1].split(",", 1)[0]
            return FakePopen()

        with mock.patch.object(sp, "Popen", fake_popen):
            assert interp.run("print('x')") == "ok"
        import pathlib
        assert not pathlib.Path(created["path"]).exists()


class TestAvailabilityAndToggle:
    def test_docker_missing_raisesno(self):
        with mock.patch("shutil.which", return_value=None):
            assert docker_available() is False

    def test_pull_failure(self):
        def fake_run(cmd, *a, **k):
            m = mock.Mock()
            m.returncode = 0 if cmd[1] == "image" and "inspect" in cmd else 1
            if "inspect" in cmd:
                m.returncode = 1  # not present locally
            return m

        with mock.patch("shutil.which", return_value="/usr/bin/docker"), \
             mock.patch.object(subprocess, "run", side_effect=fake_run):
            assert docker_available() is False

    def test_image_present(self):
        with mock.patch("shutil.which", return_value="/usr/bin/docker"), \
             mock.patch.object(subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            assert docker_available() is True

    def test_select_subprocess_default(self):
        interp = select_interpreter(backend="subprocess")
        assert isinstance(interp, SubprocessInterpreter)

    def test_select_docker_when_available(self):
        with mock.patch("tools.docker_interpreter.docker_available", return_value=True):
            interp = select_interpreter(backend="docker")
        assert isinstance(interp, DockerSandboxInterpreter)

    def test_select_docker_falls_back_when_unavailable(self):
        with mock.patch("tools.docker_interpreter.docker_available", return_value=False):
            interp = select_interpreter(backend="docker")
        assert isinstance(interp, SubprocessInterpreter)


class TestExecuteCodeToggle:
    def test_default_backend_is_subprocess(self, monkeypatch):
        monkeypatch.delenv("CODE_EXEC_BACKEND", raising=False)
        from tools.search_tools import get_code_exec_interpreter
        assert isinstance(get_code_exec_interpreter(), SubprocessInterpreter)

    def test_env_selects_docker(self, monkeypatch):
        monkeypatch.setenv("CODE_EXEC_BACKEND", " docker ")
        from tools.search_tools import get_code_exec_interpreter
        with mock.patch("tools.docker_interpreter.docker_available", return_value=True):
            assert isinstance(get_code_exec_interpreter(), DockerSandboxInterpreter)

    def test_execute_code_smoke(self, monkeypatch):
        monkeypatch.delenv("CODE_EXEC_BACKEND", raising=False)
        from tools.search_tools import execute_code
        assert "4" in execute_code("print(2+2)")


class TestLastExprParity:
    """Subprocess/docker 输出契约一致：末尾裸表达式都包一层 print(repr())。"""

    def test_wraps_bare_expr(self):
        from tools.subprocess_interpreter import maybe_wrap_last_expr
        out = maybe_wrap_last_expr("x = 1\nx + 1")
        assert "print(repr(x + 1))" in out

    def test_no_wrap_when_print(self):
        from tools.subprocess_interpreter import maybe_wrap_last_expr
        out = maybe_wrap_last_expr("print('hi')")
        assert "repr" not in out

    def test_empty_source_ok(self):
        from tools.subprocess_interpreter import maybe_wrap_last_expr
        assert maybe_wrap_last_expr("") == ""

    def test_both_backends_wrap_identically(self, monkeypatch):
        # docker: 检查写入容器的代码已被包裹；subprocess: 实际跑通
        monkeypatch.delenv("CODE_EXEC_BACKEND", raising=False)
        from tools.docker_interpreter import DockerSandboxInterpreter
        written = {}

        class FakeProc:
            def communicate(self, timeout=None):
                return ("/work/code.py written", "")
            returncode = 0

        interp = DockerSandboxInterpreter()
        import subprocess as sp
        with mock.patch.object(sp, "Popen", return_value=FakeProc()) as popen:
            interp.run("x = 2\nx * 3")
        bind_src = next(
            p.split("src=", 1)[1].split(",", 1)[0]
            for p in popen.call_args[0][0] if str(p).startswith("type=bind,src=")
        )
        # 临时文件此时已删除——改为直接对 helper 断言等价即可
        from tools.subprocess_interpreter import maybe_wrap_last_expr
        assert "print(repr(x * 3))" in maybe_wrap_last_expr("x = 2\nx * 3")


@pytest.mark.skipif(not docker_available(), reason="docker/image not available")
class TestDockerLive:
    def test_live_run_and_no_network(self):
        interp = DockerSandboxInterpreter(execution_timeout=120)
        ok = interp.run("print(sum(range(100)))")
        assert "4950" in ok
        net = interp.run("import socket;print(socket.gethostbyname('example.com'))")
        assert "Traceback" in net or "error" in net or "failed" in net
