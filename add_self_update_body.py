with open('app/main.py', 'r') as f:
    content = f.read()

# Add MemberSelfUpdateBody after MemberUpdateBody
old = '''class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None


class MemberCreateBody'''

new = '''class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None


class MemberSelfUpdateBody(BaseModel):
    """Fields a user can update about their own membership."""
    voice_code: str | None = Field(default=None, max_length=64)
    voice_label: str | None = Field(default=None, max_length=128)
    section_id: str | None = Field(default=None, max_length=191)
    notify_email: bool | None = None
    notify_osap: bool | None = None
    notify_whatsapp: bool | None = None
    notify_sms: bool | None = None


class MemberCreateBody'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)

print('Added MemberSelfUpdateBody')