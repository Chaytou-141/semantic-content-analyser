"""Original synthetic content and listeners for the isolated Linux egress lab.

Never mount a development database. No upstream requests or model loading.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import ssl
import threading
import time


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        kind = 'text/html; charset=utf-8'
        if self.path == '/robots.txt':
            kind = 'text/plain'
            body = 'User-agent: *\nAllow: /\nSitemap: https://public.fixture.invalid/sitemap.xml\n'
        elif self.path == '/sitemap.xml':
            kind = 'application/xml'
            body = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(
                f'<url><loc>https://public.fixture.invalid/articles/{i}</loc></url>' for i in (1, 2)) + '</urlset>'
        else:
            topic = 'Regular shelf cleaning and food hygiene' if self.path.endswith('/2') else 'Measuring cabinet dimensions before purchase'
            body = f'<html><head><title>{topic}</title></head><body><article><h1>{topic}</h1><p>' + (
                f'This original local fixture discusses {topic.lower()} with practical steps for cafe staff. ' * 12
            ) + '</p></article></body></html>'
        raw = body.encode()
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


class V6(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()


def udp_echo():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('0.0.0.0', 53))
        while True:
            data, peer = sock.recvfrom(512)
            sock.sendto(data, peer)


threading.Thread(target=udp_echo, daemon=True).start()
for family, host in [(ThreadingHTTPServer, '0.0.0.0'), (V6, '::')]:
    for port in [22, 53, 80, 443, 8081]:
        server = family((host, port), Handler)
        if port == 443:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain('/fixtures/ca.crt', '/fixtures/ca.key')
            server.socket = context.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
print('controlled_fixture_ready', flush=True)
while True:
    time.sleep(60)
