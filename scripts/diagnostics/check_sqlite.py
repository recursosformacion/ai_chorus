import sqlite3
conn = sqlite3.connect(':memory:')
c = conn.cursor()
c.execute('SELECT json("{\"a\": 1}")')
print('SQLite JSON:', c.fetchone())
c.execute('SELECT json_extract("{\"a\": 1}", "$.a")')
print('JSON extract:', c.fetchone())
conn.close()