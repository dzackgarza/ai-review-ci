"""The JupyterLab server on 127.0.0.1:8888 runs cells in the research container's Sage and Julia kernels."""

import json
import urllib.request
import uuid

import websocket


SERVER = "127.0.0.1:8888"


def _request(method: str, path: str, body: dict[str, str] | None = None) -> dict[str, str]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f"http://{SERVER}{path}", data=data, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    return json.loads(payload) if payload else {}


def _cell_stdout(kernel_name: str, code: str) -> str:
    kernel_id = _request("POST", "/api/kernels", {"name": kernel_name})["id"]
    try:
        channel = websocket.create_connection(
            f"ws://{SERVER}/api/kernels/{kernel_id}/channels", timeout=900,
        )
        msg_id = uuid.uuid4().hex
        channel.send(json.dumps({
            "header": {"msg_id": msg_id, "msg_type": "execute_request", "username": "test",
                       "session": uuid.uuid4().hex, "version": "5.3"},
            "parent_header": {}, "metadata": {}, "channel": "shell",
            "content": {"code": code, "silent": False, "store_history": False,
                        "user_expressions": {}, "allow_stdin": False},
        }))
        stdout = []
        status = None
        idle = False
        while status is None or not idle:
            message = json.loads(channel.recv())
            if message["parent_header"].get("msg_id") != msg_id:
                continue
            kind = message["msg_type"]
            if kind == "stream" and message["content"]["name"] == "stdout":
                stdout.append(message["content"]["text"])
            elif kind == "error":
                raise AssertionError(message["content"]["traceback"])
            elif kind == "execute_reply":
                status = message["content"]["status"]
            elif kind == "status" and message["content"]["execution_state"] == "idle":
                idle = True
        channel.close()
    finally:
        _request("DELETE", f"/api/kernels/{kernel_id}")
    assert status == "ok"
    return "".join(stdout).strip()


def test_sage_kernel_computes_a_determinant() -> None:
    assert _cell_stdout("sagemath", "print(matrix(QQ, [[2, 1], [1, 2]]).det())") == "3"


def test_julia_kernel_computes_with_oscar() -> None:
    stdout = _cell_stdout(
        "julia",
        'using Oscar; Qx, x = polynomial_ring(QQ, :x); K, a = number_field(x^2 - 2); '
        'println(degree(K), " ", a^2 == 2)',
    )
    assert stdout.splitlines()[-1] == "2 true", stdout
