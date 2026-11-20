with open('app/main.py', 'r') as f:
    content = f.read()

# Add debug print after all the dependency functions
old = '''    def current_profile(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        profile = profile_from_authorization(authorization)
        onboarding = profile.get("onboarding")
        if isinstance(onboarding, dict) and onboarding.get("required") is True:
            raise HTTPException(
                status_code=403,
                detail={"code": "ONBOARDING_REQUIRED", "onboarding": onboarding},
            )
        return profile

    def auth_call'''

new = '''    def current_profile(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        profile = profile_from_authorization(authorization)
        onboarding = profile.get("onboarding")
        if isinstance(onboarding, dict) and onboarding.get("required") is True:
            raise HTTPException(
                status_code=403,
                detail={"code": "ONBOARDING_REQUIRED", "onboarding": onboarding},
            )
        return profile
    print("DEBUG: dependencies done")

    def auth_call'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added debug after dependencies')