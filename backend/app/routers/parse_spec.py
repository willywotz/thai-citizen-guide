from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import require_permission
from app.services.parse_spec import parse_api_spec
from app.schemas.dashboard import ParseSpecRequest

router = APIRouter(prefix="/parse-spec", tags=["utilities"])


@router.post("")
async def parse_spec(
    body: ParseSpecRequest,
    auth=Depends(require_permission("agencies.write")),
):
    if not body.specText.strip():
        raise HTTPException(status_code=400, detail="specText is required")

    try:
        result = await parse_api_spec(body.specText)
        return {"success": True, "data": result}
    except ValueError as e:
        msg = str(e)
        if "Rate limit" in msg:
            raise HTTPException(status_code=429, detail=msg)
        if "Payment" in msg:
            raise HTTPException(status_code=402, detail=msg)
        raise HTTPException(status_code=500, detail=msg)
