"""
Seed router — manually populate default data.

Endpoints
---------
  POST  /seed/admin      Create default admin (admin@example.com / admin1234)
  POST  /seed/agencies   Create the 4 default government agencies
  POST  /seed/all        Run both seeders above in one call
"""

from fastapi import APIRouter, Depends
from app.auth.dependencies import require_admin

from app.auth.security import hash_password
from app.models.agency import Agency
from app.models.user import User

router = APIRouter(prefix="/seed", tags=["Seed"])

# ---------------------------------------------------------------------------
# Default data definitions
# ---------------------------------------------------------------------------

DEFAULT_ADMIN = {
    "email": "admin@example.com",
    "display_name": "Admin",
    "password": "admin1234",
    "role": "admin",
}

DEFAULT_AGENCIES = [
    {
        "name": "สำนักงานคณะกรรมการอาหารและยา",
        "short_name": "อย.",
        "logo": "🏥",
        "connection_type": "MCP",
        "status": "active",
        "description": "ระบบตรวจสอบทะเบียนยา อาหาร เครื่องสำอาง และผลิตภัณฑ์สุขภาพ",
        "data_scope": ["ทะเบียนยา", "ทะเบียนอาหาร", "เครื่องสำอาง", "ผลิตภัณฑ์สุขภาพ", "การขออนุญาต"],
        "total_calls": 12450,
        "color": "#2e9e5d",
        "endpoint_url": "https://api.fda.moph.go.th/mcp",
    },
    {
        "name": "กรมสรรพากร",
        "short_name": "กรมสรรพากร",
        "logo": "💰",
        "connection_type": "API",
        "status": "active",
        "description": "ระบบสอบถามข้อมูลภาษี การยื่นแบบ และสิทธิประโยชน์ทางภาษี",
        "data_scope": ["ภาษีเงินได้บุคคลธรรมดา", "ภาษีนิติบุคคล", "ภาษีมูลค่าเพิ่ม", "การยื่นแบบ", "สิทธิลดหย่อน"],
        "total_calls": 18320,
        "color": "#226bc3",
        "endpoint_url": "https://api.rd.go.th/v1",
    },
    {
        "name": "กรมการปกครอง",
        "short_name": "กรมการปกครอง",
        "logo": "🏛️",
        "connection_type": "A2A",
        "status": "active",
        "description": "ระบบตรวจสอบข้อมูลทะเบียนราษฎร์ บัตรประชาชน และงานปกครอง",
        "data_scope": ["ทะเบียนราษฎร์", "บัตรประจำตัวประชาชน", "ทะเบียนบ้าน", "การเปลี่ยนชื่อ", "สถานะบุคคล"],
        "total_calls": 9870,
        "color": "#ee7c2b",
        "endpoint_url": "https://api.dopa.go.th/a2a",
    },
    {
        "name": "กรมที่ดิน",
        "short_name": "กรมที่ดิน",
        "logo": "🗺️",
        "connection_type": "MCP",
        "status": "active",
        "description": "ระบบสอบถามข้อมูลที่ดิน โฉนด การจดทะเบียนสิทธิและนิติกรรม",
        "data_scope": ["โฉนดที่ดิน", "การจดทะเบียน", "ราคาประเมิน", "การรังวัด", "สิทธิและนิติกรรม"],
        "total_calls": 7650,
        "color": "#9540bf",
        "endpoint_url": "https://api.dol.go.th/mcp",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_seed_admin() -> dict:
    existing = await User.all().count()
    if existing > 0:
        return {"status": "skipped", "message": f"{existing} users already exist"}

    if await User.filter(email=DEFAULT_ADMIN["email"]).exists():
        return {"status": "skipped", "message": f"{DEFAULT_ADMIN['email']} already exists"}

    await User.create(
        email=DEFAULT_ADMIN["email"],
        display_name=DEFAULT_ADMIN["display_name"],
        hashed_password=hash_password(DEFAULT_ADMIN["password"]),
        role=DEFAULT_ADMIN["role"],
    )
    return {"status": "created", "message": f"Admin {DEFAULT_ADMIN['email']} created"}


async def _run_seed_agencies() -> dict:
    existing = await Agency.all().count()
    if existing > 0:
        return {"status": "skipped", "message": f"{existing} agencies already exist"}

    created = []
    for data in DEFAULT_AGENCIES:
        await Agency.create(**data)
        created.append(data["name"])

    return {"status": "created", "message": f"{len(created)} agencies created", "agencies": created}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/admin", summary="Seed default admin account")
async def seed_admin(_: User = Depends(require_admin)) -> dict:
    result = await _run_seed_admin()
    return result


@router.post("/agencies", summary="Seed default government agencies")
async def seed_agencies(_: User = Depends(require_admin)) -> dict:
    result = await _run_seed_agencies()
    return result


@router.post("/all", summary="Seed all default data (admin + agencies)")
async def seed_all(_: User = Depends(require_admin)) -> dict:
    admin_result = await _run_seed_admin()
    agencies_result = await _run_seed_agencies()
    return {
        "admin": admin_result,
        "agencies": agencies_result,
    }
