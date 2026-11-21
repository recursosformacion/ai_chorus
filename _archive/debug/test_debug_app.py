import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from app.config import Settings
from app.main import create_app as original_create_app

# Monkey-patch to debug
import app.main as main_module

def debug_create_app(settings=None):
    print("DEBUG: create_app called")
    cfg = settings or Settings.load()
    print("DEBUG: config loaded")
    
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        print("DEBUG: lifespan started")
        main_module.initialise_database(cfg)
        print("DEBUG: initialise_database done")
        yield
        print("DEBUG: lifespan ending")
    
    app = FastAPI(title="Chorus API", version="0.2.2", lifespan=lifespan)
    print("DEBUG: FastAPI created")
    return app

# Replace
main_module.create_app = debug_create_app

from app.main import create_app
settings = Settings.load()
app = create_app(settings)
print("App:", app)