"""Only intentional public assets may be served, even if a stray file exists."""
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

PUBLIC_ASSETS = frozenset({
    'index.html', 'app.js', 'styles.css', 'favicon.svg',
    'fonts/InstrumentSans.ttf', 'fonts/OFL.txt',
})


class PublicAssets(StaticFiles):
    async def get_response(self, path, scope):
        if path not in PUBLIC_ASSETS:
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)
