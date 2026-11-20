with open('app/main.py', 'r') as f:
    content = f.read()

# Change the path from /members/me to /members/@me
old = '@app.patch("/api/v1/groups/{group_id}/members/me")'
new = '@app.patch("/api/v1/groups/{group_id}/members/@me")'

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)

print('Changed path to @me')