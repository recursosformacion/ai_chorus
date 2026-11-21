with open('app/main.py', 'r') as f:
    content = f.read()

# Find the self-update endpoint
start = content.find('@app.patch("/api/v1/groups/{group_id}/members/@me")')
if start >= 0:
    # Find the end of this function
    lines = content[start:].split('\n')
    end_rel = 0
    for i, line in enumerate(lines[1:], 1):
        if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
            if i > 5:  # Skip the function definition
                end_rel = i
                break
    end = start + sum(len(l) + 1 for l in lines[:end_rel])
    
    # Extract the function
    func_code = content[start:end]
    print(f'Function length: {len(func_code)}')
    
    # Remove it from current location
    content = content[:start] + content[end:]
    
    # Find the manager update endpoint to insert before it
    insert_pos = content.find('@app.patch("/api/v1/groups/{group_id}/members/{user_sub}")')
    if insert_pos >= 0:
        content = content[:insert_pos] + func_code + '\n\n' + content[insert_pos:]
        with open('app/main.py', 'w') as f:
            f.write(content)
        print('Moved self-update endpoint before manager endpoint')
    else:
        print('Manager endpoint not found')
else:
    print('Self-update endpoint not found')