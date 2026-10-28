"""Library endpoints: list, upload, delete, and file-type statistics."""

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

import engine
import store.embeddings as embeddings
from sources.base import ReadOnlyLibrary
from sources.filesystem import (
    InvalidFilename,
    filesystem_source,
    get_file_type,
    safe_relative_path,
    stored_filename,
    visible_files,
)
from state import get
from store.status_db import StatusStore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/files/types")
async def get_file_types():
    """
    Get file type statistics grouped by category.
    """
    try:
        files_data = await list_uploaded_files()
        files = files_data.get("files", [])
        by_type = files_data.get("by_type", {})

        # Get detailed breakdown
        type_details = {}
        for file_type in ["document", "code", "data", "image", "other"]:
            type_files = [f for f in files if f["type"] == file_type]
            total_size = sum(f["size"] for f in type_files)

            type_details[file_type] = {
                "count": by_type.get(file_type, 0),
                "total_size": total_size,
                "files": [
                    {
                        "name": f["filename"],
                        "size": f["size"],
                        "extension": f["extension"],
                    }
                    for f in type_files[:10]  # Limit to first 10 for performance
                ],
            }

        return {
            "by_type": type_details,
            "total_files": len(files),
            "total_size": sum(f["size"] for f in files),
        }
    except Exception as e:
        logger.exception("Error getting file types")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        ) from e


@router.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    """
    Save files into the library and index them in the same request.
    """
    try:
        filesystem_source().ensure_writable("upload")
    except ReadOnlyLibrary:
        raise HTTPException(
            status_code=403,
            detail="The library is read-only. Indexing reads the mounted folder and does not upload files.",
        )
    try:
        named_files = []
        for file in files:
            try:
                named_files.append((file, stored_filename(file.filename)))
            except InvalidFilename:
                raise HTTPException(status_code=400, detail="Invalid filename")

        uploaded_files = []
        for file, safe_name in named_files:
            file_path = get().upload_dir / safe_name
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files.append(safe_name)
            logger.info(f"Uploaded file: {safe_name}")

        if engine.reindex_required():
            raise HTTPException(status_code=409, detail=embeddings.REINDEX_MESSAGE)
        engine.enqueue_ingestion("incremental")

        return {
            "message": f"Added {len(uploaded_files)} file(s) and started indexing.",
            "files": uploaded_files,
            "uploaded_count": len(uploaded_files),
            "status": "processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during file upload")
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        ) from e


@router.delete("/files/{filename:path}")
async def delete_uploaded_file(filename: str):
    """Delete one library file and only the chunks that came from that relative path."""
    try:
        filesystem_source().ensure_writable("delete")
    except ReadOnlyLibrary:
        raise HTTPException(
            status_code=403,
            detail="The library is read-only. Indexing reads the mounted folder and does not delete files.",
        )
    try:
        relative = safe_relative_path(filename)
    except InvalidFilename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = (get().upload_dir / relative).resolve()
    root = get().upload_dir.resolve()
    if not file_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        file_path.unlink()
        removed = engine.delete_chunks_for_file(relative)
    except Exception as e:
        logger.exception("Failed to delete %s", relative)
        raise HTTPException(
            status_code=500, detail="The file could not be deleted."
        ) from e

    return {"deleted": relative, "chunks_removed": removed}


@router.get("/files")
async def list_uploaded_files():
    """
    List visible files currently in the data directory, sorted by file type.
    """
    try:
        status = StatusStore(get().status_dir / "library.sqlite")
        status.open()
        files = []
        for file_path in visible_files(get().upload_dir):
            rel_path = file_path.relative_to(get().upload_dir).as_posix()
            filename = Path(rel_path).name
            file_type = get_file_type(filename)
            row = status.get("filesystem", rel_path)
            files.append(
                {
                    "name": rel_path,
                    "filename": filename,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                    "type": file_type,
                    "extension": Path(filename).suffix.lower(),
                    "index_status": None if row is None else row["status"],
                    "index_error": None if row is None else row["last_error"],
                }
            )

        # Sort by type first, then by name within each type
        type_order = {"document": 0, "code": 1, "data": 2, "image": 3, "other": 4}
        files_sorted = sorted(
            files, key=lambda x: (type_order.get(x["type"], 99), x["name"].lower())
        )

        return {
            "files": files_sorted,
            "count": len(files),
            "by_type": {
                file_type: len([f for f in files if f["type"] == file_type])
                for file_type in ["document", "code", "data", "image", "other"]
            },
        }
    except Exception as e:
        logger.exception("Error listing files in %s", get().upload_dir)
        raise HTTPException(
            status_code=500, detail="The request could not be completed."
        ) from e
