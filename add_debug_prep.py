with open('app/main.py', 'r') as f:
    content = f.read()

# Add debug print before first preparation_works endpoint
old = '''    print("DEBUG: helpers done, starting endpoints")


    @app.get("/api/v1/groups/{group_id}/preparation-works")'''

new = '''    print("DEBUG: helpers done, starting endpoints")
    print("DEBUG: ABOUT TO REGISTER PREPARATION WORKS ENDPOINTS")


    @app.get("/api/v1/groups/{group_id}/preparation-works")'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added debug before preparation endpoints')