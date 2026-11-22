"""Run a component's test suite inside the test container (a SOLVE node with backend: subprocess and container:).

stdin   {"files": {relative path: text}, "tech_profile": "python_fastapi"}
stdout  one line of JSON: {passed, failed, returncode, collected, no_tests, output, status, summary}
        (status: passed | no_tests | failed, as appgraph.build.verify.test_status)

Standard library only: the image has the project's libraries, not app-graph. The project is written to a fresh folder
under /tmp (the container's only writable place) and the suite runs there. The counting rules are
appgraph.build.verify.parse_test_output's (tests/test_build_lib.py checks the two agree).
"""
import json
import os
import re
import subprocess
import sys
import tempfile

PY_PROFILES = ("python_fastapi", "python_library", "curriculum")


def no_tests(message, returncode):
    return {"passed": 0, "failed": 0, "returncode": returncode, "collected": 0, "no_tests": True, "output": message}


def parse_test_output(out, returncode):
    passed = failed = 0
    for line in out.splitlines():
        m = re.search(r"(\d+) passed", line)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", line)
        if m:
            failed = int(m.group(1))
    collected = passed + failed
    import_error = any(tok in out for tok in ("ImportError", "ModuleNotFoundError"))
    absent = collected == 0 and returncode in (4, 5) and not import_error
    return {"passed": passed, "failed": failed, "returncode": returncode, "collected": collected,
            "no_tests": absent, "output": out[-3000:]}


def write_project(files, root):
    for rel, text in files.items():
        rel = os.path.normpath(rel).lstrip("/")
        if rel.startswith(".."):
            raise ValueError(f"unsafe path {rel!r}")
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path) or root, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def run(files, tech_profile, timeout=300):
    root = tempfile.mkdtemp(prefix="project-", dir=os.environ.get("TMPDIR", "/tmp"))
    write_project(files, root)
    if tech_profile in PY_PROFILES:
        if not os.path.isdir(os.path.join(root, "tests")):
            return no_tests("No tests/ directory in the project — nothing to verify.", 4)
        cmd = [sys.executable, "-m", "pytest", "tests/", "--tb=short", "-q", "-p", "no:cacheprovider"]
    elif tech_profile == "vue_typescript":
        if not os.path.isfile(os.path.join(root, "package.json")):
            return no_tests("No package.json in the project — nothing to verify.", 254)
        cmd = ["npm", "test"]
    else:
        return {"passed": 0, "failed": 0, "returncode": -1, "collected": 0, "no_tests": True, "output": f"Unknown profile: {tech_profile}"}
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HOME": root}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=root, timeout=timeout, env=env)
    except Exception as e:  # a crashed run is reported, not raised
        return {"passed": 0, "failed": 0, "returncode": -1, "collected": 0, "no_tests": False, "output": f"Test run errored: {e}"}
    return parse_test_output(proc.stdout + proc.stderr, proc.returncode)


def with_status(result):
    if result.get("no_tests"):
        status = "no_tests"
    elif result.get("returncode", 1) == 0 and result.get("failed", 1) == 0 and result.get("passed", 0) > 0:
        status = "passed"
    else:
        status = "failed"
    summary = f"{result.get('passed', 0)} passed, {result.get('failed', 0)} failed (exit {result.get('returncode', 1)})"
    return {**result, "status": status, "summary": summary}


if __name__ == "__main__":
    data = json.load(sys.stdin)
    print(json.dumps(with_status(run(data.get("files") or {}, data.get("tech_profile", "")))))
