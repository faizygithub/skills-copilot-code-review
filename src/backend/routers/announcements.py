"""
Announcement endpoints for the High School Management System API
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnnouncementCreate(BaseModel):
    message: str
    start_date: Optional[datetime] = None
    expiration_date: datetime


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    start_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to a JSON-serialisable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def _require_teacher(username: str) -> None:
    """Raise 401 if the username does not correspond to a known teacher."""
    if not username or not teachers_collection.find_one({"_id": username}):
        raise HTTPException(status_code=401, detail="Authentication required")


def _active_filter() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "expiration_date": {"$gte": now},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": now}},
        ],
    }


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return announcements that are currently active (within their date range)."""
    results = []
    for doc in announcements_collection.find(_active_filter()).sort("created_at", -1):
        results.append(_serialize(doc))
    return results


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------

@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str) -> List[Dict[str, Any]]:
    """Return all announcements regardless of dates. Requires teacher login."""
    _require_teacher(teacher_username)
    results = []
    for doc in announcements_collection.find().sort("created_at", -1):
        results.append(_serialize(doc))
    return results


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    announcement: AnnouncementCreate,
    teacher_username: str,
) -> Dict[str, Any]:
    """Create a new announcement. Requires teacher login."""
    _require_teacher(teacher_username)

    doc = {
        "message": announcement.message,
        "start_date": announcement.start_date,
        "expiration_date": announcement.expiration_date,
        "created_by": teacher_username,
        "created_at": datetime.now(timezone.utc),
    }
    result = announcements_collection.insert_one(doc)
    created = announcements_collection.find_one({"_id": result.inserted_id})
    return _serialize(created)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    update: AnnouncementUpdate,
    teacher_username: str,
) -> Dict[str, Any]:
    """Update an existing announcement. Requires teacher login."""
    _require_teacher(teacher_username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    if not announcements_collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Announcement not found")

    changes = {k: v for k, v in update.model_dump(exclude_unset=True).items()}
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    announcements_collection.update_one({"_id": oid}, {"$set": changes})
    updated = announcements_collection.find_one({"_id": oid})
    return _serialize(updated)


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str) -> Dict[str, Any]:
    """Delete an announcement. Requires teacher login."""
    _require_teacher(teacher_username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
