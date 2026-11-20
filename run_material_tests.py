import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

import pytest
import sys
sys.exit(pytest.main(["-v", "tests/test_material.py", "tests/test_library_integrity.py"]))