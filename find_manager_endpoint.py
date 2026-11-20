with open('app/main.py', 'r') as f:
    content = f.read()

# Find the manager update endpoint
idx = content.find('@app.patch("/api/v1/groups/{group_id}/members/{user_sub}")')
if idx >= 0:
    print(f'Found at {idx}')
    # Print context
    print(content[max(0,idx-200):idx+200])