with open('app/main.py', 'r') as f:
    content = f.read()

# Find "return app" right before the module-level app = create_app()
# We need to find the one that's inside the function
idx = content.rfind('return app\n\n\napp = create_app()')
if idx < 0:
    idx = content.rfind('return app')
    print("Found at:", idx)
    print("Context:", content[idx-100:idx+100])
else:
    print("Found pattern at:", idx)
    # Add debug print before return app
    new_content = content[:idx] + '    print("DEBUG: returning app")\n    ' + content[idx:]
    with open('app/main.py', 'w') as f:
        f.write(new_content)
    print("Added debug print")