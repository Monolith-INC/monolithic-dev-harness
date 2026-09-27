from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from integrations import transport

SERVER = textwrap.dedent(
    """
    import json, sys
    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        if message["method"] == "initialize":
            reply = {"protocolVersion": "2024-11-05"}
        elif message["method"] == "tools/list":
            reply = {"tools": [{"name": "echo"}]}
        elif message["params"]["name"] == "fail":
            reply = {"isError": True, "content": [{"type": "text", "text": json.dumps({"code": "nope", "message": "no"})}]}
        else:
            text = "<<n>> [UNTRUSTED] <<n>>\\n" + json.dumps(message["params"]["arguments"]) + "\\n<</n>>"
            reply = {"content": [{"type": "text", "text": text}]}
        print("log line that is not a reply")
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": reply}), flush=True)
    """
)


class TransportTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.server = Path(self._tmp.name) / "server.py"
        self.server.write_text(SERVER)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_call_round_trips_through_a_real_server_process(self) -> None:
        call = transport.mcp(sys.executable, (str(self.server),), timeout=10)
        self.assertEqual(call("echo", {"a": 1}).value, {"a": 1})
        failed = call("fail", {})
        self.assertEqual((failed.failure.code, failed.failure.message), ("nope", "no"))
        exchange = transport.process_exchange(sys.executable, (str(self.server),), 10)
        self.assertEqual(transport.list_tools(exchange).value, ({"name": "echo"},))

    def test_a_missing_command_or_a_silent_server_fails_cleanly(self) -> None:
        self.assertEqual(
            transport.mcp("/no/such/command", ())("x", {}).failure.code,
            "provider_unavailable",
        )
        silent = transport.mcp(
            sys.executable, ("-c", "import time; time.sleep(5)"), timeout=0.3
        )
        self.assertEqual(silent("x", {}).failure.code, "provider_timeout")

    def test_decoding_keeps_plain_text_and_unfences_json(self) -> None:
        self.assertEqual(transport.decode("hello", None), "hello")
        self.assertEqual(transport.decode("<<a>> x <<a>>\n[1]\n<</a>>", None), [1])
        self.assertEqual(transport.failure_from_text("oops").code, "provider_error")


class LargeReplyTest(unittest.TestCase):
    def test_a_large_reply_after_many_log_lines_is_read(self) -> None:
        server = textwrap.dedent(
            """
            import json, sys
            for line in sys.stdin:
                message = json.loads(line)
                if "id" not in message:
                    continue
                if message["method"] != "initialize":
                    sys.stdout.write("log\\n" * 5000)
                text = json.dumps({"blob": "x" * 3_000_000})
                reply = {"content": [{"type": "text", "text": text}]}
                print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": reply}), flush=True)
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.py"
            path.write_text(server)
            reply = transport.mcp(sys.executable, (str(path),), timeout=30)("big", {})
            self.assertEqual(len(reply.value["blob"]), 3_000_000)
