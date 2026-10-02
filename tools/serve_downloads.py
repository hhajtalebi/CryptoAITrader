"""درگاه کوچک دانلود سورس؛ فقط بستهٔ معرفی‌شده ارائه می‌شود، نه پوشهٔ پروژه.

اجرا: python tools/serve_downloads.py --directory /path/to/delivery --port 8080
پوشهٔ تحویل باید release.json و ZIP معرفی‌شده در آن را داشته باشد.
این ابزار مستقل از دسکتاپ، SQLite و کلیدهای کاربر است و وابستگی اضافی ندارد.
"""

from __future__ import annotations

import argparse
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).with_name("download_page.html")


def load_release(directory: Path) -> tuple[dict, Path]:
    """مسیر و جمع کنترلی بسته قبل از بازشدن درگاه تأیید می‌شوند."""
    directory = directory.resolve()
    raw = json.loads((directory / "release.json").read_text(encoding="utf-8"))
    filename = raw["filename"]
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.zip", filename):
        raise ValueError("Invalid release filename")
    archive = directory / filename
    if archive.is_symlink() or archive.resolve().parent != directory or not archive.is_file():
        raise ValueError("Archive must be a regular file inside the delivery directory")
    with archive.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != raw["sha256"] or archive.stat().st_size != raw["size_bytes"]:
        raise ValueError("Release size or SHA-256 does not match the archive")
    # فقط فرادادهٔ عمومیِ مشخص، نه هر کلید احتمالیِ فایل ورودی.
    release = {key: raw[key] for key in (
        "version", "filename", "sha256", "size_bytes", "file_count", "date", "tests"
    )}
    return release, archive


def make_handler(directory: Path) -> type[BaseHTTPRequestHandler]:
    """مسیریابی allowlist؛ پیمایش پوشه/دسترسی به فایل دلخواه وجود ندارد."""
    release, archive = load_release(directory)
    values = {
        "VERSION": release["version"], "FILENAME": release["filename"],
        "SHA256": release["sha256"], "SIZE": f'{release["size_bytes"] / 1024 / 1024:.2f}',
        "FILES": release["file_count"], "DATE": release["date"], "TESTS": release["tests"],
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    page = re.sub(r"\{\{([A-Z0-9_]+)\}\}",
                  lambda match: html.escape(str(values[match[1]])), template).encode("utf-8")
    metadata = json.dumps(release, ensure_ascii=False, indent=2).encode("utf-8")
    checksum = f'{release["sha256"]}  {release["filename"]}\n'.encode("ascii")
    font = ROOT / "assets/fonts/Vazirmatn-Regular.ttf"

    class DownloadHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._respond(head=False)

        def do_HEAD(self) -> None:
            self._respond(head=True)

        def _respond(self, *, head: bool) -> None:
            path = urlsplit(self.path).path
            payload = None
            file_path = None
            disposition = None
            status = 200
            if path in {"/", "/index.html"}:
                payload, content_type = page, "text/html; charset=utf-8"
            elif path == "/release.json":
                payload, content_type = metadata, "application/json; charset=utf-8"
            elif path == "/SHA256SUMS.txt":
                payload, content_type = checksum, "text/plain; charset=utf-8"
                disposition = 'attachment; filename="SHA256SUMS.txt"'
            elif path == "/download.zip":
                file_path, content_type = archive, "application/zip"
                disposition = f'attachment; filename="{release["filename"]}"'
            elif path == "/font.ttf" and font.is_file():
                file_path, content_type = font, "font/ttf"
            else:
                status = 404
                payload, content_type = b"Not found", "text/plain; charset=utf-8"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_path.stat().st_size if file_path else len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            if disposition:
                self.send_header("Content-Disposition", disposition)
            self.end_headers()
            if not head:
                try:
                    if file_path:
                        with file_path.open("rb") as handle:
                            shutil.copyfileobj(handle, self.wfile)
                    else:
                        self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # لغو دانلود توسط مرورگر نباید سرور را متوقف کند.

    return DownloadHandler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True, help="Delivery directory, not source/data")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), make_handler(args.directory)) as server:
        print(f"Download page listening on {args.host}:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
