import hashlib
from pathlib import Path
from typing import Tuple
from app.core.config import settings

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit
PDF_MAGIC_BYTES = b"%PDF-"


def get_pdf_storage_dir() -> Path:
    """Returns the directory where uploaded PDFs are stored, creating it if needed."""
    storage_base = Path(settings.LOCAL_STORAGE_PATH)
    if not storage_base.is_absolute():
        # Anchor relative to backend directory or project root
        storage_base = Path.cwd() / settings.LOCAL_STORAGE_PATH

    pdf_dir = storage_base / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir


def calculate_sha256(content: bytes) -> str:
    """Computes the SHA-256 hexadecimal digest for raw file bytes."""
    hasher = hashlib.sha256()
    hasher.update(content)
    return hasher.hexdigest()


def validate_pdf_content(content: bytes) -> None:
    """
    Validates file size and magic bytes.
    Raises ValueError with explanatory message on invalid input.
    """
    if len(content) == 0:
        raise ValueError("The uploaded file is empty (0 bytes).")

    if len(content) > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise ValueError(f"File size exceeds the maximum allowed limit of {max_mb} MB.")

    if not content.startswith(PDF_MAGIC_BYTES):
        raise ValueError("Invalid file format. The file does not have a valid PDF header (%PDF-).")


def save_pdf_to_disk(content: bytes) -> Tuple[str, str, int]:
    """
    Validates and persists PDF bytes to the configured storage directory.
    Stores the file deterministically named after its SHA-256 hash.

    Returns:
        (file_path_str, file_checksum_sha256, file_size_bytes)
    """
    validate_pdf_content(content)
    checksum = calculate_sha256(content)
    file_size = len(content)

    pdf_dir = get_pdf_storage_dir()
    target_path = pdf_dir / f"{checksum}.pdf"

    # Only write if it does not already exist on disk
    if not target_path.exists():
        with open(target_path, "wb") as f:
            f.write(content)

    return str(target_path), checksum, file_size
