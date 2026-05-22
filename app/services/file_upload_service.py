"""Reusable file upload service"""
import os
import shutil
from uuid import uuid4
from typing import Tuple
from fastapi import UploadFile, HTTPException


ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx'}


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def save_upload(file: UploadFile, dest_folder: str, prefix: str = None) -> Tuple[str, str]:
    """Save uploaded file to dest_folder.

    Returns (original_filename, saved_path)
    Raises HTTPException on invalid file type or IO errors.
    """
    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    ensure_dir(dest_folder)

    unique = uuid4().hex
    base = os.path.splitext(file.filename)[0]
    safe_base = base.replace(' ', '_')[:200]
    if prefix:
        saved_name = f"{safe_base}_{prefix}_{unique}{ext}"
    else:
        saved_name = f"{safe_base}_{unique}{ext}"

    saved_path = os.path.join(dest_folder, saved_name)

    try:
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    return file.filename, saved_path
