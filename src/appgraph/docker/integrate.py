#!/usr/bin/env python3
"""System integration inside the test container (baked into appgraph-verify:py3.12 as /usr/local/bin/appgraph-integrate).

stdin   {"files": {path: text} of the backend, "tests": {application id: acceptance script}, "port": 8000}
stdout  one line of JSON: {server: ready|timeout, results: {app: "PASS" | "FAIL: <tail>"}, report, passed, server_log}

Standard library only. The backend is written to /tmp/backend and started with uvicorn on 127.0.0.1:<port> (the container
has no network, but it has a loopback); each acceptance script runs against it with a time limit; the server dies with the
container, so no run can leave it behind. graph-code started it on the host and stopped it at the end of the workflow.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def write_tree(files, root):
    for rel, text in files.items():
        rel = os.path.normpath(rel).lstrip("/")
        if rel.startswith(".."):
            raise ValueError(f"unsafe path {rel!r}")
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path) or root, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def wait_for_http(url, timeout_s):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except urllib.error.HTTPError:
            return True                       # it answered
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return False


def main(data):
    tmp = os.environ.get("TMPDIR", "/tmp")
    backend = tempfile.mkdtemp(prefix="backend-", dir=tmp)
    write_tree(data.get("files") or {}, backend)
    port = str(data.get("port") or 8000)
    env = {**os.environ, "HOME": backend, "PYTHONDONTWRITEBYTECODE": "1"}
    log_path = os.path.join(tmp, "server.log")
    with open(log_path, "w") as log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port],
                                  cwd=backend, stdout=log, stderr=subprocess.STDOUT, env=env)
    results = {}
    try:
        ready = wait_for_http(f"http://127.0.0.1:{port}/docs", float(data.get("startup_s") or 20))
        if ready:
            tests_dir = tempfile.mkdtemp(prefix="acceptance-", dir=tmp)
            for app, code in (data.get("tests") or {}).items():
                path = os.path.join(tests_dir, f"test_acceptance_{app}.py")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(code)
                try:
                    done = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=60, env=env)
                    results[app] = "PASS" if done.returncode == 0 else f"FAIL: {(done.stdout + done.stderr)[-2000:]}"
                except subprocess.TimeoutExpired:
                    results[app] = "FAIL: timed out after 60s"
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    with open(log_path) as f:
        server_log = f.read()[-3000:]
    if not ready:
        report = "FAILED: backend server did not start"
    else:
        report = "\n".join(f"- {'PASS' if r == 'PASS' else 'FAIL'} {app}" + ("" if r == "PASS" else f": {r[6:].strip()[:500]}")
                           for app, r in results.items())
    passed = ready and all(r == "PASS" for r in results.values())
    return {"server": "ready" if ready else "timeout", "results": results, "report": report, "passed": passed,
            "server_log": server_log}


if __name__ == "__main__":
    print(json.dumps(main(json.load(sys.stdin))))
