with open('app/main.py', 'r') as f:
    content = f.read()

# Add debug print at start of create_app
old = 'def create_app(settings: Settings | None = None) -> FastAPI:\n    cfg = settings or Settings.load()'
new = '''def create_app(settings: Settings | None = None) -> FastAPI:
    print("DEBUG: create_app START")
    cfg = settings or Settings.load()'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added debug print at start')