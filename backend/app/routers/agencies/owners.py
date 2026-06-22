"""Owner-scoped endpoints: assign owner, list owned agencies."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.authz import authorize_or_403, grant
from app.auth.dependencies import get_current_user
from app.models.agency import Agency
from app.models.relationship import Relationship
from app.models.user import User
from app.routers.agencies._utils import _with_health
from app.schemas.agency import AgencyResponse
from app.services.audit import record_audit

router = APIRouter()


class AddOwnerRequest(BaseModel):
    user_id: str


@router.post("/{agency_id}/owners", summary="Assign an owner to an agency (admin)")
async def add_agency_owner(agency_id: str, body: AddOwnerRequest, user: User = Depends(get_current_user)):
    agency = await Agency.get_or_none(id=agency_id)
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    await authorize_or_403(user, "user:manage", agency)
    await grant(body.user_id, "owner", "agency", agency.id)
    await record_audit(user, "agency.add_owner", object_type="agency", object_id=agency.id, detail={"owner_user_id": body.user_id})
    return {"detail": "owner added"}


@router.get("/mine", response_model=list[AgencyResponse], summary="Agencies owned by the current user")
async def list_my_agencies(user: User = Depends(get_current_user)) -> list[AgencyResponse]:
    ids = await Relationship.filter(
        subject_type="user", subject_id=user.id, relation="owner", object_type="agency"
    ).values_list("object_id", flat=True)
    agencies = await Agency.filter(id__in=list(ids))
    return [await _with_health(a) for a in agencies]
