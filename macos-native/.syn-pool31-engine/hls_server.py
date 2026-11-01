#!/usr/bin/env python3
"""Loopback-only HTTP server for a single shared HLS directory."""
import functools, http.server, os, pathlib, sys
folder=pathlib.Path(sys.argv[1]).resolve()
portfile=pathlib.Path(sys.argv[2]).resolve()
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_): pass
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        super().end_headers()
handler=functools.partial(Quiet, directory=str(folder))
with http.server.ThreadingHTTPServer(('127.0.0.1',0),handler) as srv:
    tmp=portfile.with_suffix('.tmp')
    tmp.write_text(str(srv.server_port))
    os.replace(tmp,portfile)
    srv.serve_forever(poll_interval=0.3)
