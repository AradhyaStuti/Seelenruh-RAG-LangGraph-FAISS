"""Manual MongoDB Atlas connectivity diagnostic. NOT a pytest test —
unit tests live in `server/tests/` and are run with `pytest`.

Run after filling in MONGODB_URI in .env:
    cd server && .venv/Scripts/python verify_db.py

It will:
  1. Connect to Atlas (with a clear error if the URI / password / IP is wrong).
  2. Print the cluster host so you know you reached the right one.
  3. List databases + collections (proves R access).
  4. Insert + read + delete a test document in seelenruh.users (proves R/W access).
  5. Show what gets stored when someone signs up via the auth route.
"""
import asyncio
import sys
import bcrypt

import db
from auth import hash_password
from config import MONGODB_URI, MONGODB_DB


def fatal(msg: str) -> None:
    print(f"\n❌ {msg}\n")
    sys.exit(1)


async def main() -> None:
    if not MONGODB_URI:
        fatal("MONGODB_URI is empty in .env — paste your Atlas connection string first.")
    if "<db_password>" in MONGODB_URI:
        fatal("MONGODB_URI still has the literal '<db_password>' placeholder. Replace it with your actual Atlas user password.")

    print(f"Connecting to Atlas (db={MONGODB_DB})...")
    ok = await db.connect()
    if not ok:
        fatal("Atlas connect failed. Common causes: wrong password, your IP not allowed in Atlas Network Access, cluster paused. Check the error printed above.")

    print(f"\n✅ Connected.\n")

    # Check db + collections
    db_handle = db.users().database
    cols = await db_handle.list_collection_names()
    print(f"Collections in {MONGODB_DB}: {cols or '(empty — they get created on first write)'}\n")

    # Write + read test in users
    test_email = "smoke-test@seelenruh.app"
    await db.users().delete_one({"email": test_email})  # clean slate

    test_doc = {
        "email": test_email,
        "name": "Smoke Test",
        "password": hash_password("hunter22"),
    }
    print("Inserting test user...")
    result = await db.users().insert_one(test_doc)
    print(f"  inserted _id={result.inserted_id}")

    fetched = await db.users().find_one({"email": test_email})
    print(f"  fetched name={fetched['name']}")
    assert bcrypt.checkpw(b"hunter22", fetched["password"].encode()), "bcrypt verify failed"
    print(f"  bcrypt verify: OK")

    await db.users().delete_one({"email": test_email})
    print(f"  cleaned up\n")

    user_count = await db.users().count_documents({})
    msg_count = await db.messages().count_documents({})
    print(f"Current document counts in {MONGODB_DB}:")
    print(f"  users:    {user_count}")
    print(f"  messages: {msg_count}\n")

    print("✅ All checks passed. Signup / login / chat history will now persist to Atlas.\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
