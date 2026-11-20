import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from app.config import Settings
from app.main import create_app as original_create_app

# Test the original create_app step by step
import app.main as main_module

# Check if there's an issue with the lifespan
settings = Settings.load()
cfg = settings

print("Testing initialise_database...")
main_module.initialise_database(cfg)
print("OK")

print("Testing _connect...")
conn = main_module._connect(cfg)
print("OK:", conn)
conn.close()

print("All basic functions work. Now testing create_app...")
app = original_create_app(settings)
print("App:", app)