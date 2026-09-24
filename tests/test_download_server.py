"""آزمون HTTP درگاه دانلود؛ بدون Qt، شبکهٔ بیرونی یا فایل واقعی کاربر."""

import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import threading
import zipfile

import pytest

from tools.serve_downloads import load_release, make_handler


@pytest.fixture()
def delivery(tmp_path):
    archive = tmp_path / "CryptoAITrader-test.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("CryptoAITrader/README.md", "test-only")
    metadata = dict(version="2.2.2", filename=archive.name,
                    sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    size_bytes=archive.stat().st_size, file_count=1,
                    date="2026-09-23", tests="synthetic test")
    (tmp_path / "release.json").write_text(json.dumps(metadata))
    (tmp_path / ".env").write_text("MUST_NOT_BE_SERVED")
    return tmp_path, metadata, archive


@pytest.fixture()
def server(delivery):
    directory, _, _ = delivery
    with ThreadingHTTPServer(("127.0.0.1", 0), make_handler(directory)) as instance:
        thread = threading.Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            yield instance.server_port
        finally:
            instance.shutdown()
            thread.join(timeout=5)


def request(port, path, method="GET"):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, headers={"Host": "download-preview.e2b.app"})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def test_download_exact_bytes_and_headers(server, delivery):
    _, metadata, archive = delivery
    status, headers, body = request(server, "/download.zip")
    assert status == 200 and body == archive.read_bytes()
    assert headers["Content-Type"] == "application/zip"
    assert headers["Content-Disposition"] == f'attachment; filename="{archive.name}"'
    assert int(headers["Content-Length"]) == len(body)
    assert hashlib.sha256(body).hexdigest() == metadata["sha256"]
    status, headers, body = request(server, "/download.zip", "HEAD")
    assert status == 200 and body == b""
    assert int(headers["Content-Length"]) == archive.stat().st_size


def test_page_and_checksum_work_with_preview_host(server, delivery):
    status, _, body = request(server, "/")
    text = body.decode()
    assert status == 200 and 'dir="rtl"' in text
    assert 'href="/download.zip"' in text and "{{" not in text
    assert "2.2.2" in text
    status, _, body = request(server, "/SHA256SUMS.txt")
    assert status == 200 and delivery[1]["sha256"].encode() in body
    status, _, body = request(server, "/release.json")
    assert status == 200 and json.loads(body) == delivery[1]


@pytest.mark.parametrize("path", ["/.env", "/.git/config", "/../release.json",
    "/%2e%2e/.env", "/README.md", "/CryptoAITrader-test.zip", "/data/crypto_ai_trader.db"])
def test_only_allowlisted_routes_are_served(server, path):
    status, _, body = request(server, path)
    assert status == 404 and b"MUST_NOT_BE_SERVED" not in body


def test_wrong_hash_is_refused_before_listening(delivery):
    directory, _, archive = delivery
    archive.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA-256"):
        load_release(directory)


@pytest.mark.parametrize("filename", ["../private.zip", "/private.zip", "bad\\private.zip"])
def test_manifest_cannot_select_file_outside_delivery(delivery, filename):
    directory, metadata, _ = delivery
    metadata["filename"] = filename
    (directory / "release.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="filename"):
        load_release(directory)


def test_html_escapes_metadata_and_json_excludes_unknown_fields(delivery):
    directory, metadata, _ = delivery
    metadata["tests"] = '<script>alert("x")</script>'
    metadata["private_note"] = "not-public"
    (directory / "release.json").write_text(json.dumps(metadata))
    release, _ = load_release(directory)
    assert "private_note" not in release
    with ThreadingHTTPServer(("127.0.0.1", 0), make_handler(directory)) as instance:
        thread = threading.Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            status, _, body = request(instance.server_port, "/")
            assert status == 200 and b"&lt;script&gt;" in body
            assert b"<script>" not in body and b"not-public" not in body
        finally:
            instance.shutdown()
            thread.join(timeout=5)
