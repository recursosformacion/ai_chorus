import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from app.main import create_app
from app.config import Settings
settings = Settings.load()
app = create_app(settings)
print('App:', app)