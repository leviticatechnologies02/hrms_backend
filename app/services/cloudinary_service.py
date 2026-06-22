"""
Cloudinary Service
Handles cloud-based file uploads to Cloudinary so that profile photos and
other uploaded files persist across Render restarts/redeploys.

Falls back to local disk storage when CLOUDINARY_URL is not set (local dev).
"""

import os
import io
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Check if Cloudinary credentials are configured
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

_cloudinary_enabled = False

# Try to import and configure cloudinary
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api

    if CLOUDINARY_URL:
        cloudinary.config(cloudinary_url=CLOUDINARY_URL)
        _cloudinary_enabled = True
        logger.info("✅ Cloudinary configured via CLOUDINARY_URL")
    elif CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True,
        )
        _cloudinary_enabled = True
        logger.info("✅ Cloudinary configured via individual credentials")
    else:
        logger.warning(
            "⚠️  Cloudinary not configured — set CLOUDINARY_URL or "
            "CLOUDINARY_CLOUD_NAME + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET "
            "env vars. Falling back to local disk storage."
        )
except ImportError:
    logger.warning(
        "⚠️  cloudinary package not installed. "
        "Run: pip install cloudinary  — Falling back to local disk storage."
    )


def is_cloudinary_enabled() -> bool:
    """Return True if Cloudinary is configured and ready to use."""
    return _cloudinary_enabled


def upload_image(
    file_bytes: bytes,
    filename: str,
    folder: str = "hrms/profile_photos",
    public_id: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """
    Upload image bytes to Cloudinary.

    Returns:
        (success: bool, url: str, public_id: str)
        On failure returns (False, "", "")
    """
    if not _cloudinary_enabled:
        return False, "", ""

    try:
        # Build upload options
        upload_opts = {
            "folder": folder,
            "resource_type": "image",
            "overwrite": True,
            "invalidate": True,
            "format": "webp",          # Convert to webp for smaller size
            "quality": "auto:good",    # Auto quality optimization
            "fetch_format": "auto",
        }
        if public_id:
            upload_opts["public_id"] = public_id

        result = cloudinary.uploader.upload(
            io.BytesIO(file_bytes),
            **upload_opts,
        )

        url = result.get("secure_url", "")
        pid = result.get("public_id", "")
        logger.info(f"✅ Cloudinary upload success: {url}")
        return True, url, pid

    except Exception as e:
        logger.error(f"❌ Cloudinary upload failed: {e}")
        return False, "", ""


def delete_image(public_id: str) -> bool:
    """
    Delete an image from Cloudinary by its public_id.

    Returns True on success, False on failure.
    """
    if not _cloudinary_enabled or not public_id:
        return False

    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="image")
        return result.get("result") == "ok"
    except Exception as e:
        logger.error(f"❌ Cloudinary delete failed for {public_id}: {e}")
        return False


def get_optimized_url(public_id: str, width: int = 200, height: int = 200) -> str:
    """
    Generate an optimized thumbnail URL for a Cloudinary image.
    """
    if not _cloudinary_enabled or not public_id:
        return ""
    try:
        from cloudinary import CloudinaryImage
        return CloudinaryImage(public_id).build_url(
            width=width,
            height=height,
            crop="fill",
            gravity="face",
            quality="auto",
            fetch_format="auto",
        )
    except Exception:
        return ""
