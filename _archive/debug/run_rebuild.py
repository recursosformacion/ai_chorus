import os
os.environ["CHORUS_DATABASE_URL"] = "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test"

import subprocess
result = subprocess.run(["python", "scripts/rebuild_test_db.py"], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
print("Return code:", result.returncode)