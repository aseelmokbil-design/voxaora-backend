import psycopg2
conn = psycopg2.connect("postgresql://voxaora:voxaora_pass@localhost:5432/voxaora_db")
cur = conn.cursor()
cur.execute("SELECT id, phone, full_name, role, status FROM users ORDER BY created_at LIMIT 20")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()
