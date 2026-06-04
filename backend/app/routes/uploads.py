import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

uploads_bp = Blueprint("uploads", __name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def get_upload_dir():
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def build_image_payload(filename, original_filename, content_type, size):
    return {
        "filename": filename,
        "original_filename": original_filename,
        "content_type": content_type,
        "size": size,
        "path": f"uploads/{filename}",
        "url": f"{request.host_url.rstrip('/')}/api/uploads/image/{filename}",
    }


@uploads_bp.post("/api/uploads/image")
def upload_image():
    if "image" not in request.files:
        return jsonify({"status": "error", "error": "請選擇要上傳的圖片。"}), 400

    image_file = request.files["image"]
    if not image_file or not image_file.filename:
        return jsonify({"status": "error", "error": "圖片檔名不可為空。"}), 400

    original_filename = secure_filename(image_file.filename)
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"status": "error", "error": "只支援 jpg、jpeg、png、webp 圖片。"}), 400

    content_type = image_file.mimetype or ""
    if content_type not in ALLOWED_IMAGE_MIME_TYPES:
        return jsonify({"status": "error", "error": "圖片格式不支援，請上傳 jpg、png 或 webp。"}), 400

    image_file.stream.seek(0, 2)
    size = image_file.stream.tell()
    image_file.stream.seek(0)

    max_size = current_app.config["MAX_IMAGE_UPLOAD_BYTES"]
    if size > max_size:
        max_mb = max_size // (1024 * 1024)
        return jsonify({"status": "error", "error": f"圖片太大，請上傳 {max_mb}MB 以內的檔案。"}), 413

    filename = f"{uuid.uuid4().hex}{extension}"
    upload_dir = get_upload_dir()
    image_file.save(upload_dir / filename)

    return (
        jsonify(
            {
                "status": "ok",
                "image": build_image_payload(filename, original_filename, content_type, size),
            }
        ),
        201,
    )


@uploads_bp.get("/api/uploads/image/<path:filename>")
def get_uploaded_image(filename):
    safe_name = secure_filename(filename)
    if safe_name != filename:
        return jsonify({"status": "error", "error": "invalid filename"}), 400

    return send_from_directory(get_upload_dir(), safe_name)
