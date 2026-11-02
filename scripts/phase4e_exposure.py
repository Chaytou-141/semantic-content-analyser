"""Raw localhost HTTPS exposure checks, against an already-owned disposable lab."""
import hashlib
import http.client
import socket
import urllib.request


PRIVATE_PATHS = [
    '/semantic_analyser/api.py','/app/semantic_analyser/api.py','/Dockerfile',
    '/.env','/release.env','/deploy/aws/.env','/.git/config','/.git/HEAD',
    '/runtime/workspace.sqlite3','/workspace.sqlite3','/runtime/visitors/',
    '/logs/server.log','/runtime/server.log','/proc/self/environ','/run/egress/status.json',
    '/static/.env','/static/release.env','/static/private.py','/static/workspace.sqlite3',
    '/static/.git/config','/static/logs/server.log','/static/../semantic_analyser/api.py',
    '/static/%2e%2e/semantic_analyser/api.py','/static/..%2fsemantic_analyser%2fapi.py',
    '/static/%252e%252e%252fsemantic_analyser%252fapi.py',
    '/docs','/redoc','/openapi.json','/debug','/_debug','/api/debug','/api/openapi.json',
]
PUBLIC_PATHS = ['/','/static/app.js','/static/styles.css','/static/favicon.svg',
                '/static/fonts/InstrumentSans.ttf','/static/fonts/OFL.txt']


def audit_routes(context, browser, private_values):
    request=urllib.request.Request('https://localhost:8443/')
    for handler in browser.handlers:
        if isinstance(handler,urllib.request.HTTPCookieProcessor):handler.cookiejar.add_cookie_header(request)
    cookie=request.get_header('Cookie')
    assert cookie,'Authenticated test browser required'
    rows=[]
    class LocalHTTPS(http.client.HTTPSConnection):
        def connect(self):
            # Explicit loopback transport avoids slow IPv6 localhost fallback on
            # Windows. Certificate verification still uses the hostname localhost.
            self.sock=context.wrap_socket(socket.create_connection(('127.0.0.1',8443),timeout=5),server_hostname='localhost')
    for authenticated in [False,True]:
        for path in PRIVATE_PATHS+PUBLIC_PATHS:
            connection=LocalHTTPS('localhost',8443,context=context,timeout=5)
            try:
                connection.request('GET',path,headers={'Cookie':cookie if authenticated else '', 'X-Workspace-Request':'true'})
                response=connection.getresponse();body=response.read(2_000_001)
                assert len(body)<=2_000_000
                assert all(value.encode() not in body for value in private_values)
                assert b'Traceback (most recent call last)' not in body
                assert response.status==200 if path in PUBLIC_PATHS else response.status in {400,401,403,404}
                rows.append({'authenticated':authenticated,'path':path,'status':response.status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
            finally:connection.close()
    return {'requests':len(rows),'private_values_returned':0,'raw_paths_not_normalized_by_client':True,
            'all_public_assets_accessible':True,'rows':rows,
            'intentional_endpoints':'Authenticated article/CSV exports and saved-demo evaluation remain application features, not debug/file-serving routes.'}
