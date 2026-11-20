import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from app.main import create_app
from app.config import Settings

settings = Settings.load()
print("Creating app...")
try:
    app = create_app(settings)
    print("App created:", app)
except Exception as e:
    print("ERROR creating app:", e)
    import traceback
    traceback.print_exc()