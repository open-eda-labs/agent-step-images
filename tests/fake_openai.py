"""Servidor falso de Chat Completions (stdlib, SSE) para testar o harness sem modelo: cada POST devolve o próximo passo do roteiro.

Uso: python fake_openai.py <porta> <roteiro.json>; roteiro = lista de {"tool": nome, "args": {...}} ou {"text": "..."}; o último se repete.
Grava em requests.jsonl (ao lado do roteiro) a última mensagem de cada requisição, para o teste conferir o que chegou ao "modelo".
"""

import http.server
import itertools
import json
import pathlib
import sys

SCRIPT = pathlib.Path(sys.argv[2])
STEPS = json.loads(SCRIPT.read_text())
LOG = SCRIPT.with_name("requests.jsonl")
counter = itertools.count()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        i = next(counter)
        step = STEPS[min(i, len(STEPS) - 1)]
        with LOG.open("a") as f:
            f.write(json.dumps({"i": i, "model": body["model"], "auth": self.headers.get("Authorization"), "messages": body["messages"]}) + "\n")
        if "tool" in step:
            call = {"index": 0, "id": f"call_{i}", "type": "function", "function": {"name": step["tool"], "arguments": json.dumps(step["args"])}}
            delta, finish = {"role": "assistant", "tool_calls": [call]}, "tool_calls"
        else:
            delta, finish = {"role": "assistant", "content": step["text"]}, "stop"
        chunk = lambda d, f: "data: " + json.dumps({"id": "x", "object": "chat.completion.chunk", "created": 0, "model": body["model"],
                                                   "choices": [{"index": 0, "delta": d, "finish_reason": f}]}) + "\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write((chunk(delta, None) + chunk({}, finish) + "data: [DONE]\n\n").encode())


http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
