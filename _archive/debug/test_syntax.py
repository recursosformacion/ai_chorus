import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

from app.config import Settings
from app.main import create_app as original_create_app

# Test the original create_app with debug prints inside
import app.main as main_module

# We need to trace through the original function. Let's check if there's a syntax error
# in the file by trying to compile it.
import py_compile
try:
    py_compile.compile('app/main.py', doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print("SYNTAX ERROR:", e)