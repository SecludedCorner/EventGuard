"""Explicit foreground MCP bridge entry point; default config cannot serve."""
from pathlib import Path
import argparse
import json
import os
import sys
import threading

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT))


def main(argv=None):
    from contrib.mcp_bridge.app import load_config,create_app
    parser=argparse.ArgumentParser(description="EventGuard synthetic-only MCP bridge; disabled by default")
    parser.add_argument("--config",default="config/bridge.example.json")
    subs=parser.add_subparsers(dest="command",required=True)
    subs.add_parser("check")
    serving=subs.add_parser("serve")
    serving.add_argument("--enable-server",action="store_true")
    args=parser.parse_args(argv)
    try:
        from eventguard.runtime import safe_child
        path=safe_child(ROOT,args.config)
        config=load_config(path)
        if args.command=="check":
            print(json.dumps({"config_valid":True,"enabled":config["enabled"],"network_enabled":config["network_enabled"],
                              "synthetic_only":True,"listener_started":False,"credentials_read":False,
                              "dpapi_platform_available":os.name=="nt","real_agent_woken":False}))
            return 0
        if not args.enable_server or not config["enabled"]:
            print(json.dumps({"error":"explicit_enable_and_approved_config_required","listener_started":False}))
            return 2
        app=create_app(ROOT,config)
        from wsgiref.simple_server import WSGIServer,WSGIRequestHandler,make_server
        class BoundedServer(WSGIServer):
            request_queue_size=5
            def get_request(self):
                sock,address=super().get_request()
                sock.settimeout(5)
                return sock,address
        class QuietHandler(WSGIRequestHandler):
            def log_message(self,*unused):
                pass  # Never log bearer headers, callbacks, payloads or untrusted request paths.
        stop=threading.Event()
        def worker():
            while not stop.is_set():
                try:app.delivery_worker_status=app.service.pump_once()["status"]
                except Exception:app.delivery_worker_status="storage_or_transport_fault"
                stop.wait(1)
        server=make_server(config["listen_host"],config["listen_port"],app,server_class=BoundedServer,handler_class=QuietHandler)
        thread=threading.Thread(target=worker,name="EventGuard-delivery",daemon=False)
        thread.start()
        print(json.dumps({"state":"serving_loopback","synthetic_only":True,"real_agent_woken":False}),flush=True)
        try:
            server.serve_forever(poll_interval=.5)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            server.server_close()
            thread.join()
        print(json.dumps({"state":"stopped","worker_exited":not thread.is_alive()}))
        return 0
    except (ValueError,OSError,RuntimeError):
        print(json.dumps({"error":"bridge_configuration_or_runtime_unavailable","listener_started":False}))
        return 4


if __name__=="__main__":
    raise SystemExit(main())
