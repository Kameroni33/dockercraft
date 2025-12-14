"""
Create an admin password hash for Dockercraft
"""
from passlib.context import CryptContext
import sys

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if len(sys.argv) < 2:
    print("Usage: python create-admin.py <password>")
    sys.exit(1)

password = sys.argv[1]
hashed = pwd_context.hash(password)

print("\nAdd this to your .env file:")
print(f"ADMIN_PASSWORD_HASH={hashed}")
print("\nOr use this in config.py:")
print(f'admin_password_hash: str = "{hashed}"')
