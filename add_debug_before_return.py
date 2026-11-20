with open('app/main.py', 'r') as f:
    content = f.read()

# Add debug print before return app
old = '    return app\n\n\napp = create_app()'
new = '''    print("DEBUG: about to return app")
    return app

app = create_app()'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added debug print before return')