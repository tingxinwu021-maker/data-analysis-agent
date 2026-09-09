"""文件上传接口：POST /upload"""
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..agent.code_agent import UPLOAD_DIR, infer_schema

router = APIRouter(tags=["files"])

ALLOWED = {".csv", ".xlsx", ".xls"}


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=400, detail=f"仅支持 {ALLOWED} 类型文件")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    path = UPLOAD_DIR / file_id
    path.write_bytes(await file.read())

    try:
        schema = infer_schema(path)
    except Exception as e:  # noqa: BLE001
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"无法解析文件：{e}")

    return {"file_id": file_id, "filename": file.filename, "schema": schema}
