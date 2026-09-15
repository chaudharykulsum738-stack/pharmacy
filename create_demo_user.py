from werkzeug.security import generate_password_hash
from db import get_connection

DEMO_EMAIL = "demo@pharmacy.com"
DEMO_PASSWORD = "demo1234"

conn = get_connection()
cursor = conn.cursor()

password_hash = generate_password_hash(DEMO_PASSWORD)
cursor.execute(
    "UPDATE users SET password_hash = ? WHERE email = ?",
    (password_hash, DEMO_EMAIL)
)
conn.commit()

print(f"Updated password hash for {DEMO_EMAIL}")
print(f"You can now log in with email='{DEMO_EMAIL}' and password='{DEMO_PASSWORD}'")

cursor.close()
conn.close()
