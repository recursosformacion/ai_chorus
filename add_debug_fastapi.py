with open('app/main.py', 'r') as f:
    content = f.read()

# Add debug print after FastAPI creation
old = '''    app = FastAPI(title="Chorus API", version="0.2.2", lifespan=lifespan)

    origins = list(cfg.cors_origins)'''

new = '''    app = FastAPI(title="Chorus API", version="0.2.2", lifespan=lifespan)
    print("DEBUG: FastAPI created")

    origins = list(cfg.cors_origins)'''

content = content.replace(old, new)

with open('app/main.py', 'w') as f:
    f.write(content)
print('Added debug after FastAPI')