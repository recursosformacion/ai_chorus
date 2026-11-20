import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from app.config import Settings
from app.main import create_app as original_create_app

# Monkey-patch to add debug
import app.main as main_module

original_create_app_func = main_module.create_app

def debug_create_app(settings=None):
    print("DEBUG: create_app START")
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
    
    # Copy the rest of the original function but with try/except
    # We'll just test if we can reach the end
    try:
        # Test a simple endpoint registration
        @app.get("/test")
        def test_endpoint():
            return {"ok": True}
        print("DEBUG: Simple endpoint registered")
        
        # Now try to import the rest of the module's endpoint registrations
        # This is hard to do incrementally. Let's check if there's a syntax error
        # by looking at the original function's bytecode or by running it in parts.
        
        print("DEBUG: About to return app")
        return app
    except Exception as e:
        print("DEBUG: Exception in create_app:", e)
        import traceback
        traceback.print_exc()
        return None

main_module.create_app = debug_create_app

from app.main import create_app
settings = Settings.load()
app = create_app(settings)
print("App:", app)