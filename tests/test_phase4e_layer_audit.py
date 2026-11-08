import importlib.util
import io
import gzip
from pathlib import Path
import tarfile

spec=importlib.util.spec_from_file_location('layer_audit',Path(__file__).resolve().parents[1]/'scripts/phase4e_image_audit.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_deleted_layer_secret_is_still_detected_across_chunk_boundary():
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as archive:
        body=b'x'*(1024*1024-10)+module.CANARY
        item=tarfile.TarInfo('app/.env');item.size=len(body);archive.addfile(item,io.BytesIO(body))
        # A whiteout cannot erase the credential from this historical layer.
        archive.addfile(tarfile.TarInfo('app/.wh..env'))
    stream.seek(0)
    with tarfile.open(fileobj=stream,mode='r|') as archive:result=module.scan_layer(archive)
    assert result['canary_files']==['app/.env']
    assert result['sensitive_first_party_paths']==['app/.env']


def test_tiny_compressed_layer_is_not_skipped_and_root_secret_path_is_preserved():
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as layer:
        body=module.CANARY;item=tarfile.TarInfo('./.env');item.size=len(body);layer.addfile(item,io.BytesIO(body))
    compressed=gzip.compress(stream.getvalue());assert len(compressed)<10240
    outer=io.BytesIO()
    with tarfile.open(fileobj=outer,mode='w') as archive:
        item=tarfile.TarInfo('blobs/sha256/example');item.size=len(compressed);archive.addfile(item,io.BytesIO(compressed))
        item=tarfile.TarInfo('manifest.json');item.size=2;archive.addfile(item,io.BytesIO(b'{}'))
    outer.seek(0);result=module.scan_archive(outer)
    assert len(result)==1 and result[0]['canary_files']==['.env']
    assert result[0]['sensitive_first_party_paths']==['.env']


def test_known_credential_path_is_detected_without_a_known_value():
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as archive:
        item=tarfile.TarInfo('root/.aws/credentials');item.size=7;archive.addfile(item,io.BytesIO(b'unknown'))
    stream.seek(0)
    with tarfile.open(fileobj=stream,mode='r|') as archive:result=module.scan_layer(archive)
    assert result['sensitive_first_party_paths']==['root/.aws/credentials']
