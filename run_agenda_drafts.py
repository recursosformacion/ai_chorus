import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

import pytest
import sys
sys.exit(pytest.main(["-v", "tests/test_agenda.py", "tests/test_creation_drafts.py", "tests/test_creation_drafts_mysql.py"]))