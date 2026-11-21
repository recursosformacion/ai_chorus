with open('app/main.py', 'r') as f:
    content = f.read()

# Find the end of group_members GET endpoint to add the self-update endpoint after it
idx = content.find('def group_members(')
if idx >= 0:
    # Find the end of this function (next @app. or def )
    next_app = content.find('\n@app.', idx + 100)
    if next_app == -1:
        next_app = content.find('\ndef ', idx + 100)
    print(content[idx:next_app])