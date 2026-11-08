"""Sensitive files must remain inaccessible even if accidentally placed in web/."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from semantic_analyser.public_assets import PublicAssets, PUBLIC_ASSETS


def test_public_asset_allowlist_blocks_real_stray_files(tmp_path):
    files=['app.js','.env','release.env','workspace.sqlite3','private.py','.git/config','logs/server.log']
    for name in files:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('public-js' if name=='app.js' else 'SYNTHETIC_PRIVATE_CANARY')
    app=FastAPI();app.mount('/static',PublicAssets(directory=tmp_path))
    with TestClient(app) as client:
        assert client.get('/static/app.js?v=1').text=='public-js'
        for name in files[1:]:
            response=client.get('/static/'+name)
            assert response.status_code==404 and 'SYNTHETIC_PRIVATE_CANARY' not in response.text


@pytest.mark.parametrize('path',['/static/%2e%2e/private.py','/static/..%2fprivate.py','/static/%252e%252e%252fprivate.py','/static/fonts/../../private.py','/static/fonts%5c..%5cprivate.py','/static/fonts%5c..%5cInstrumentSans.ttf'])
def test_encoded_traversal_is_not_a_public_asset(tmp_path,path):
    (tmp_path/'private.py').write_text('SYNTHETIC_PRIVATE_CANARY')
    app=FastAPI();app.mount('/static',PublicAssets(directory=tmp_path))
    with TestClient(app) as client:
        response=client.get(path)
        assert response.status_code==404 and 'SYNTHETIC_PRIVATE_CANARY' not in response.text


def test_all_intended_assets_exist_and_debug_routes_are_disabled(client):
    assert client.app.debug is False
    for name in PUBLIC_ASSETS:assert client.get('/static/'+name).status_code==200
    for path in ['/docs','/redoc','/openapi.json','/debug','/_debug']:
        assert client.get(path).status_code==404
