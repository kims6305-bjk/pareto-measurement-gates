"""Issue #6: CLI resolution and demo output survive Windows-style encodings."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]


def test_cli_resolution_and_cp949_demos(monkeypatch):
    scripts = ROOT / "gate" / "scripts"
    spec = importlib.util.spec_from_file_location("instrument_check_run", scripts / "instrument_check_run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    command = []
    monkeypatch.setattr(module.shutil, "which", lambda name: r"C:\\tools\\claude.CMD" if name == "claude" else None)

    def fake_run(args, **kwargs):
        command.extend(args)
        return SimpleNamespace(stdout='{"label":"SUPPORTED","rationale":"ok"}', returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    assert module.call("check")[0] == "SUPPORTED"
    assert command[0] == r"C:\\tools\\claude.CMD"

    # subprocess.run is monkeypatched only on the module object above; restore it
    # before invoking real Python processes for the console-encoding regression.
    monkeypatch.undo()
    env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp949:strict")
    for path in (ROOT / "gate/reach_check.py", ROOT / "gate/harness_diet.py"):
        result = subprocess.run([sys.executable, str(path), "--demo"],
                                env=env, capture_output=True, timeout=30)
        assert result.returncode == 0, (str(path), result.stderr.decode("cp949", errors="replace"))
        assert b"OK - 6 cases" in result.stdout
