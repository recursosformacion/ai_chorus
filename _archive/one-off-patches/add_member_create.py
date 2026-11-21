with open('app/main.py', 'r') as f:
    content = f.read()

# Add MemberCreateBody after MemberUpdateBody
old = '''class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None

class GroupRoleBody'''

new = '''class MemberUpdateBody(BaseModel):
    role: Literal["manager", "member"] | None = None
    admin_role_id: str | None = None
    musical_role_id: str | None = None
    section_id: str | None = None
    status: Literal["active", "removed"] | None = None


class MemberCreateBody(BaseModel):
    user_sub: str = Field(min_length=1, max_length=191)
    role: Literal["manager", "member"] = "member"
    admin_role_id: str | None = Field(default=None, max_length=191)
    musical_role_id: str | None = Field(default=None, max_length=191)
    section_id: str | None = Field(default=None, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)

class GroupRoleBody'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)

print('Added MemberCreateBody')