"""LinkedIn Marketing API v2 — post publishing with image support."""

from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
API_VERSION = "202502"


def _access_token() -> str:
    return os.getenv("LINKEDIN_ACCESS_TOKEN", "")


def _person_id() -> str:
    return os.getenv("LINKEDIN_PERSON_ID", "")


def _headers(content_type: str = "application/json") -> dict:
    return {
        "Authorization": f"Bearer {_access_token()}",
        "Content-Type": content_type,
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": API_VERSION,
    }


def build_post_payload(person_id: str, text: str, media_urn: str | None = None) -> dict:
    """Build the LinkedIn post API payload, optionally with an image or document."""
    payload = {
        "author": f"urn:li:person:{person_id}",
        "lifecycleState": "PUBLISHED",
        "visibility": "PUBLIC",
        "commentary": text,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
        },
    }

    if media_urn:
        media_obj = {"id": media_urn}
        # Documents need a title field
        if ":document:" in media_urn:
            media_obj["title"] = "Carousel.pdf"
        payload["content"] = {"media": media_obj}

    return payload


async def _upload_image(image_path: str) -> str | None:
    """Upload an image to LinkedIn. Returns the image URN or None on failure.

    LinkedIn image upload flow:
    1. POST /rest/images?action=initializeUpload → get uploadUrl + image URN
    2. PUT uploadUrl with image bytes
    """
    person_id = _person_id()
    if not person_id:
        return None

    async with httpx.AsyncClient(timeout=60) as client:
        # Step 1: Initialize upload
        init_payload = {
            "initializeUploadRequest": {
                "owner": f"urn:li:person:{person_id}",
            }
        }
        resp = await client.post(
            f"{LINKEDIN_API_BASE}/images?action=initializeUpload",
            json=init_payload,
            headers=_headers(),
        )

        if resp.status_code not in (200, 201):
            logger.error("Image init failed %d: %s", resp.status_code, resp.text[:300])
            return None

        data = resp.json()
        upload_url = data["value"]["uploadUrl"]
        image_urn = data["value"]["image"]
        logger.info("Image upload initialized: %s", image_urn)

        # Step 2: Upload image binary
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        resp2 = await client.put(
            upload_url,
            content=image_bytes,
            headers={
                "Authorization": f"Bearer {_access_token()}",
                "Content-Type": "application/octet-stream",
            },
        )

        if resp2.status_code in (200, 201):
            logger.info("Image uploaded: %s (%d bytes)", image_urn, len(image_bytes))
            return image_urn
        else:
            logger.error("Image upload failed %d: %s", resp2.status_code, resp2.text[:300])
            return None


async def _upload_document(doc_path: str) -> str | None:
    """Upload a PDF document to LinkedIn. Returns the document URN or None.

    LinkedIn document upload flow:
    1. POST /rest/documents?action=initializeUpload → get uploadUrl + document URN
    2. PUT uploadUrl with PDF bytes
    """
    person_id = _person_id()
    if not person_id:
        return None

    async with httpx.AsyncClient(timeout=60) as client:
        # Step 1: Initialize upload
        init_payload = {
            "initializeUploadRequest": {
                "owner": f"urn:li:person:{person_id}",
            }
        }
        resp = await client.post(
            f"{LINKEDIN_API_BASE}/documents?action=initializeUpload",
            json=init_payload,
            headers=_headers(),
        )

        if resp.status_code not in (200, 201):
            logger.error("Document init failed %d: %s", resp.status_code, resp.text[:300])
            return None

        data = resp.json()
        upload_url = data["value"]["uploadUrl"]
        doc_urn = data["value"]["document"]
        logger.info("Document upload initialized: %s", doc_urn)

        # Step 2: Upload PDF binary
        with open(doc_path, "rb") as f:
            doc_bytes = f.read()

        resp2 = await client.put(
            upload_url,
            content=doc_bytes,
            headers={
                "Authorization": f"Bearer {_access_token()}",
                "Content-Type": "application/octet-stream",
            },
        )

        if resp2.status_code in (200, 201):
            logger.info("Document uploaded: %s (%d bytes)", doc_urn, len(doc_bytes))
            return doc_urn
        else:
            logger.error("Document upload failed %d: %s", resp2.status_code, resp2.text[:300])
            return None


async def _upload_video(video_path: str) -> str | None:
    """Upload a video to LinkedIn. Returns the video URN or None.

    LinkedIn video upload flow:
    1. POST /rest/videos?action=initializeUpload → get uploadUrls + video URN
    2. PUT each chunk to its upload URL, collect ETags
    3. POST /rest/videos?action=finalizeUpload with ETags
    """
    person_id = _person_id()
    if not person_id:
        return None

    file_size = os.path.getsize(video_path)
    logger.info("Uploading video: %s (%d bytes)", video_path, file_size)

    async with httpx.AsyncClient(timeout=300) as client:
        # Step 1: Initialize upload
        init_payload = {
            "initializeUploadRequest": {
                "owner": f"urn:li:person:{person_id}",
                "fileSizeBytes": file_size,
                "uploadCaptions": False,
                "uploadThumbnail": False,
            }
        }
        resp = await client.post(
            f"{LINKEDIN_API_BASE}/videos?action=initializeUpload",
            json=init_payload,
            headers=_headers(),
        )
        if resp.status_code not in (200, 201):
            logger.error("Video init failed %d: %s", resp.status_code, resp.text[:300])
            return None

        data = resp.json()["value"]
        video_urn = data["video"]
        upload_token = data["uploadToken"]
        upload_instructions = data["uploadInstructions"]
        logger.info("Video upload initialized: %s (%d chunks)", video_urn, len(upload_instructions))

        # Step 2: Upload each chunk, collect ETags
        etags = []
        with open(video_path, "rb") as f:
            for part in upload_instructions:
                first_byte = part["firstByte"]
                last_byte = part["lastByte"]
                f.seek(first_byte)
                chunk = f.read(last_byte - first_byte + 1)

                resp2 = await client.put(
                    part["uploadUrl"],
                    content=chunk,
                    headers={
                        "Authorization": f"Bearer {_access_token()}",
                        "Content-Type": "application/octet-stream",
                    },
                )
                if resp2.status_code not in (200, 201):
                    logger.error("Video chunk upload failed %d: %s", resp2.status_code, resp2.text[:300])
                    return None
                etags.append(resp2.headers.get("etag", ""))

        # Step 3: Finalize upload
        finalize_payload = {
            "finalizeUploadRequest": {
                "video": video_urn,
                "uploadToken": upload_token,
                "uploadedPartIds": etags,
            }
        }
        resp3 = await client.post(
            f"{LINKEDIN_API_BASE}/videos?action=finalizeUpload",
            json=finalize_payload,
            headers=_headers(),
        )
        if resp3.status_code not in (200, 201):
            logger.error("Video finalize failed %d: %s", resp3.status_code, resp3.text[:300])
            return None

        logger.info("Video uploaded and finalized: %s", video_urn)
        return video_urn




def download_youtube_video(url: str, output_dir: str = "/tmp") -> str | None:
    """Download YouTube video via Apify. Returns local MP4 path or None."""
    import re
    import subprocess

    apify_token = os.getenv("APIFY_TOKEN", "")
    if not apify_token:
        logger.warning("No APIFY_TOKEN — skipping video download")
        return None

    try:
        import time

        # Step 1: Start Apify actor run
        logger.info("Starting Apify YouTube download: %s", url[:60])
        resp = httpx.post(
            f"https://api.apify.com/v2/acts/streamers~youtube-video-downloader/runs?token={apify_token}",
            json={"videos": [{"url": url}], "quality": "lowest"},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            logger.error("Apify run failed %d: %s", resp.status_code, resp.text[:200])
            return None

        run_data = resp.json().get("data", resp.json())
        run_id = run_data.get("id")
        if not run_id:
            logger.error("No run ID in Apify response")
            return None

        logger.info("Apify run started: %s — polling for completion...", run_id)

        # Step 1b: Poll until SUCCEEDED or failed (max 5 minutes)
        for i in range(30):
            time.sleep(10)
            poll_resp = httpx.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}?token={apify_token}",
                timeout=15,
            )
            if poll_resp.status_code != 200:
                continue
            status = poll_resp.json().get("data", {}).get("status", "")
            logger.info("Apify poll %d: %s", i + 1, status)
            if status == "SUCCEEDED":
                run_data = poll_resp.json().get("data", {})
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                logger.error("Apify run failed: %s", status)
                return None
        else:
            logger.error("Apify run timed out after 5 minutes")
            return None

        dataset_id = run_data.get("defaultDatasetId")
        if not dataset_id:
            logger.error("No dataset ID in Apify response")
            return None

        # Step 2: Get download URL from dataset
        resp2 = httpx.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={apify_token}",
            timeout=30,
        )
        items = resp2.json()
        if not items:
            logger.error("Empty Apify dataset")
            return None

        download_url = items[0].get("downloadedFileUrl", "")
        if not download_url:
            logger.error("No downloadedFileUrl in Apify response")
            return None

        logger.info("Apify file URL: %s", download_url[:80])

        # Step 3: Download the file from Apify storage
        ext = download_url.rsplit(".", 1)[-1].split("?")[0] if "." in download_url else "webm"
        raw_path = os.path.join(output_dir, f"linkedin_video.{ext}")
        mp4_path = os.path.join(output_dir, "linkedin_video.mp4")

        with httpx.stream("GET", download_url, timeout=120, follow_redirects=True) as stream:
            stream.raise_for_status()
            with open(raw_path, "wb") as f:
                for chunk in stream.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

        size_mb = os.path.getsize(raw_path) / (1024 * 1024)
        logger.info("Downloaded from Apify: %.1f MB (%s)", size_mb, ext)

        # Skip if too large (Render free tier has 512MB RAM)
        if size_mb > 50:
            logger.error("Video too large (%.1f MB) — skipping to avoid OOM", size_mb)
            os.remove(raw_path)
            return None

        # Step 4: Convert to mp4 if needed (LinkedIn requires mp4)
        if ext == "mp4":
            return raw_path

        try:
            # Use lightweight remux first (no re-encoding, low RAM)
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", raw_path, "-c", "copy", "-movflags", "+faststart", mp4_path],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and os.path.exists(mp4_path):
                mp4_size = os.path.getsize(mp4_path) / (1024 * 1024)
                logger.info("Remuxed to MP4: %.1f MB", mp4_size)
                os.remove(raw_path)
                return mp4_path

            # Remux failed — try minimal re-encode with low memory settings
            logger.warning("Remux failed, trying lightweight re-encode...")
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", raw_path,
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                 "-c:a", "aac", "-b:a", "64k",
                 "-vf", "scale=640:-2",
                 "-movflags", "+faststart",
                 "-threads", "1",
                 mp4_path],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0 and os.path.exists(mp4_path):
                mp4_size = os.path.getsize(mp4_path) / (1024 * 1024)
                logger.info("Re-encoded to MP4: %.1f MB", mp4_size)
                os.remove(raw_path)
                return mp4_path
            else:
                logger.error("ffmpeg re-encode failed: %s", result.stderr[:200])
                return raw_path
        except FileNotFoundError:
            logger.warning("ffmpeg not installed, using %s directly", ext)
            return raw_path

    except Exception as e:
        logger.error("Apify video download failed: %s", e)
        return None


async def publish_post(text: str, image_path: str | None = None, document_path: str | None = None, video_path: str | None = None) -> dict:
    """Publish a post to LinkedIn with optional image.

    Returns {"success": bool, "post_id": str, "error": str}.
    """
    token = _access_token()
    person_id = _person_id()

    if not token or not person_id:
        return {"success": False, "post_id": "", "error": "Missing LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_ID"}

    # Upload media: video > document > image (priority order)
    media_urn = None

    # Video takes top priority (native video = best reach)
    if not media_urn and video_path and os.path.exists(video_path):
        logger.info("Uploading video: %s", video_path)
        media_urn = await _upload_video(video_path)
        if media_urn:
            logger.info("Video ready: %s", media_urn)
        else:
            logger.warning("Video upload failed, falling back to document/image")

    # Document (carousel) if no video
    if not media_urn and document_path and os.path.exists(document_path):
        logger.info("Uploading document: %s", document_path)
        media_urn = await _upload_document(document_path)
        if media_urn:
            logger.info("Document ready: %s", media_urn)
        else:
            logger.warning("Document upload failed, falling back to image")

    # Image as last resort
    if not media_urn and image_path and os.path.exists(image_path):
        logger.info("Uploading image: %s", image_path)
        media_urn = await _upload_image(image_path)
        if media_urn:
            logger.info("Image ready: %s", media_urn)
        else:
            logger.warning("Image upload failed, posting without media")

    payload = build_post_payload(person_id, text, media_urn=media_urn)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LINKEDIN_API_BASE}/posts",
            json=payload,
            headers=_headers(),
        )

        if resp.status_code in (200, 201):
            post_id = resp.headers.get("x-restli-id", "")
            logger.info("Published to LinkedIn: %s (with media: %s)", post_id, bool(media_urn))
            return {"success": True, "post_id": post_id, "error": ""}
        else:
            error = resp.text[:300]
            logger.error("LinkedIn publish failed %d: %s", resp.status_code, error)
            return {"success": False, "post_id": "", "error": f"HTTP {resp.status_code}: {error}"}
