from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB per file
MAX_BATCH_BYTES = 60 * 1024 * 1024  # 60 MB total per upload request

# Block dangerous extensions that could contain executable code or script payloads
DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".bash", ".ps1", ".vbs", ".js", ".mjs",
    ".py", ".pyw", ".php", ".phtml", ".jsp", ".jspx", ".asp", ".aspx", ".cgi",
    ".pl", ".dll", ".so", ".dylib", ".scr", ".msi", ".jar", ".reg", ".com",
    ".hta", ".cpl", ".pif", ".gadget", ".wsf", ".bin", ".elf", ".app", ".dmg"
}

# Strictly permitted document, tabular, visual, and audio extensions
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".eml", ".csv", ".pdf", ".docx", ".xlsx", ".xls", ".zip",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
    ".mp3", ".wav", ".m4a", ".ogg", ".webm", ".weba", ".aac", ".flac",
    ".wma", ".wmb", ".wmv"
}

# Windows reserved device filenames (case-insensitive)
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10))
}


def sanitize_filename(filename: str) -> str:
    """Sanitizes filename against path traversal, null bytes, and illegal characters."""
    if not filename:
        return "unnamed_document.txt"

    # Remove null bytes and control chars
    clean = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    # Extract only the base name (prevents ../ or C:\ path traversal)
    clean = Path(clean).name
    # Strip dangerous shell/path characters
    clean = re.sub(r'[<>:"/\\|?*]', "_", clean).strip(". ")

    if not clean:
        return "unnamed_document.txt"

    # Check for Windows device names like CON.txt or AUX
    stem = Path(clean).stem.upper()
    if stem in WINDOWS_RESERVED_NAMES:
        clean = f"safe_{clean}"

    # Truncate length if overly long
    if len(clean) > 180:
        ext = Path(clean).suffix
        clean = clean[: 180 - len(ext)] + ext

    return clean


def verify_file_content_signature(ext: str, data: bytes) -> Tuple[bool, str]:
    """Verifies that the raw byte header matches the declared file extension.
    Prevents executable or malicious files renamed with a benign extension."""
    if not data:
        return False, "File is completely empty."

    # 1. PDF
    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            return False, "Secured file check failed: Invalid PDF magic byte header."
        return True, ""

    # 2. Images
    if ext == ".png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, "Secured file check failed: Invalid PNG magic bytes."
        return True, ""

    if ext in (".jpg", ".jpeg"):
        if not (data.startswith(b"\xff\xd8\xff") or data[:2] == b"\xff\xd8"):
            return False, "Secured file check failed: Invalid JPEG magic bytes."
        return True, ""

    if ext == ".gif":
        if not (data.startswith(b"GIF87a") or data.startswith(b"GIF89a")):
            return False, "Secured file check failed: Invalid GIF magic bytes."
        return True, ""

    if ext == ".webp":
        if not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
            return False, "Secured file check failed: Invalid WebP RIFF/WEBP header."
        return True, ""

    # 3. Zip-based office archives (DOCX, XLSX, ZIP)
    if ext in (".docx", ".xlsx", ".zip"):
        if not data.startswith(b"PK\x03\x04"):
            return False, f"Secured file check failed: File '{ext}' is not a valid ZIP/Office container."
        return True, ""

    # 4. Audio
    if ext == ".wav":
        if not (data.startswith(b"RIFF") and data[8:12] == b"WAVE"):
            return False, "Secured file check failed: Invalid WAV RIFF/WAVE header."
        return True, ""

    if ext == ".ogg":
        if not data.startswith(b"OggS"):
            return False, "Secured file check failed: Invalid OGG header."
        return True, ""

    if ext == ".flac":
        if not data.startswith(b"fLaC"):
            return False, "Secured file check failed: Invalid FLAC header."
        return True, ""

    if ext in (".webm", ".weba"):
        if not data.startswith(b"\x1a\x45\xdf\xa3"):
            return False, "Secured file check failed: Invalid WebM/EBML container signature."
        return True, ""

    # 5. Plain Text, CSV, Markdown, EML
    if ext in (".txt", ".md", ".csv", ".eml"):
        # Ensure it does not start with executable signatures (MZ for Windows PE/EXE, \x7fELF for Linux)
        if data.startswith(b"MZ") or data.startswith(b"\x7fELF") or data.startswith(b"\xca\xfe\xba\xbe"):
            return False, "Secured file check failed: Executable binary disguised as plain text."
        # Check for presence of excessive binary null bytes in first 512 bytes
        sample = data[:512]
        if b"\x00" in sample:
            return False, "Secured file check failed: Binary null bytes detected in text document."
        return True, ""

    # Allowed by default for other extensions
    return True, ""


def validate_file_upload(raw_filename: str, data: bytes) -> Tuple[bool, str, str]:
    """Complete validation pipeline for an uploaded file.
    Returns: (is_valid, sanitized_name, error_message)"""
    safe_name = sanitize_filename(raw_filename)
    ext = Path(safe_name).suffix.lower()

    if not ext:
        return False, safe_name, "File must have a valid file extension."

    if ext in DANGEROUS_EXTENSIONS:
        return False, safe_name, f"Security violation: Executable or script file type '{ext}' is forbidden."

    if ext not in ALLOWED_EXTENSIONS:
        return False, safe_name, f"File type '{ext}' is not permitted for requirements analysis."

    if len(data) > MAX_FILE_BYTES:
        return False, safe_name, f"File exceeds maximum allowed size of {MAX_FILE_BYTES // (1024 * 1024)}MB."

    is_valid_sig, sig_err = verify_file_content_signature(ext, data)
    if not is_valid_sig:
        return False, safe_name, sig_err

    return True, safe_name, ""
