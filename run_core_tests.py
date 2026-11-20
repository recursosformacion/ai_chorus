import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

import pytest
import sys
sys.exit(pytest.main(["-v", "tests/test_articles.py", "tests/test_group_roles.py", "tests/test_group_social_links.py", "tests/test_legacy_uploads.py", "tests/test_activity_log.py"]))