from pydantic import BaseModel, Field


class PortalSignupRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = Field(..., description="portal role: public, hospital, ambulance, government")
    subRole: str | None = Field(default=None, description="hospital/government sub-role")
    location: str | None = None
    phone: str | None = None

    regNumber: str | None = None
    hospitalType: str | None = None
    departmentRole: str | None = None

    governmentLevel: str | None = None

    ambulanceBase: str | None = None
    vehicleId: str | None = None


class PortalLoginRequest(BaseModel):
    email: str | None = None
    password: str
    role: str
    hospitalId: str | None = None


class PortalLoginResponse(BaseModel):
    token: str
    user: dict
