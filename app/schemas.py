from datetime import date
from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    organization_name: str
    organization_code: str
    name: str
    email: EmailStr
    password: str = Field(min_length=8)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class AssessmentIn(BaseModel):
    indicator_id: int
    score: int = Field(ge=0, le=100)
    observation: str = ""
    campus_id: int | None = None
    department_id: int | None = None

class ActionIn(BaseModel):
    domain_code: str
    title: str
    description: str = ""
    owner_id: int | None = None
    due_date: date | None = None
    priority: str = "Medium"

class EvidenceIn(BaseModel):
    assessment_id: int | None = None
    file_name: str
    storage_key: str
    mime_type: str = ""

class CampusIn(BaseModel):
    name: str

class DepartmentIn(BaseModel):
    campus_id: int
    name: str

class UserIn(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "consultant"

class ActionStatusIn(BaseModel):
    status: str

class OrgProfileIn(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    principal_name: str | None = None
    academic_year: str | None = None
    student_strength: str | None = None
