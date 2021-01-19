import socketserver
import threading

from http.server import SimpleHTTPRequestHandler
from http.server import HTTPServer


handler = SimpleHTTPRequestHandler
httpd = HTTPServer(("", 8081), handler)
httpd_thread = threading.Thread(target=httpd.serve_forever())
httpd_thread.setDaemon(True)
httpd_thread.start()

print("done")