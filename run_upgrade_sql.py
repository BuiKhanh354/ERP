"""Execute UpgradeDatabase.sql against ERP_DB using pyodbc."""
import pyodbc
import os
import re

SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'UpgradeDatabase.sql')

# Read SQL file
with open(SQL_FILE, 'r', encoding='utf-8') as f:
    sql_content = f.read()

# Split by GO statements (SQL Server batch separator)
# Handle various GO formats: standalone line, with trailing whitespace/comments
batches = re.split(r'^\s*GO\s*$', sql_content, flags=re.MULTILINE | re.IGNORECASE)
batches = [b.strip() for b in batches if b.strip()]

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=BVK354;"
    "DATABASE=ERP_DB;"
    "Trusted_Connection=yes;"
)

print("Connecting to ERP_DB...")
conn = pyodbc.connect(conn_str, autocommit=True)
cursor = conn.cursor()

print(f"Executing {len(batches)} SQL batches...")
success = 0
errors = 0
for i, batch in enumerate(batches, 1):
    if not batch.strip() or batch.strip().startswith('--'):
        print(f"  Batch {i}/{len(batches)} SKIPPED (comment/empty)")
        continue
    try:
        cursor.execute(batch)
        while cursor.nextset():
            pass
        print(f"  Batch {i}/{len(batches)} OK")
        success += 1
    except Exception as e:
        print(f"  Batch {i}/{len(batches)} ERROR: {e}")
        print(f"  SQL preview: {batch[:150]}...")
        errors += 1

cursor.close()
conn.close()
print(f"\nDone! Success: {success}, Errors: {errors}")
