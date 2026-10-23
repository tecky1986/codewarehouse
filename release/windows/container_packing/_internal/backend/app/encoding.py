from urllib.parse import quote

class EncodingError(Exception):
    pass


def decode_bytes(raw: bytes) -> tuple[str, str]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            text = raw.decode(enc)
            return text, enc
        except UnicodeDecodeError:
            continue
    raise EncodingError("无法识别编码")


def content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "download.bin"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8-sig")
