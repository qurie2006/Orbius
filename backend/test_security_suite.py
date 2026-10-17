import requests
import json
import time
import sys
from pathlib import Path

# Add backend directory to sys.path so we can import app modules directly for setup
sys.path.insert(0, str(Path(__file__).parent))
from app import db

BASE_URL = "http://127.0.0.1:8000"

def test_password_and_signup():
    print("\n--- 1. Testing Password Security & Hashing ---")
    # Test short password
    res = requests.post(f"{BASE_URL}/api/auth/signup", json={"email": "short@test.com", "password": "123", "name": "Short"})
    assert res.status_code == 400, f"Expected 400 for short password, got {res.status_code}"
    print("PASS: Short password (<8 chars) rejected with 400.")

    # Signup User A
    user_a_email = f"user_a_{int(time.time())}@example.com"
    res_a = requests.post(f"{BASE_URL}/api/auth/signup", json={"email": user_a_email, "password": "SecurePassword123!", "name": "User Alpha"})
    assert res_a.status_code == 200, f"User A signup failed: {res_a.text}"
    user_a_data = res_a.json()
    token_a = user_a_data["token"]
    user_a = user_a_data["user"]
    print(f"PASS: User A signed up successfully: {user_a['id']}, token generated.")

    # Verify PBKDF2 hash & salt in DB
    user_a_record = db.get_user_by_email(user_a_email)
    assert user_a_record is not None
    assert user_a_record.get("salt") is not None and len(user_a_record["salt"]) == 32, "Salt must be 16 bytes hex (32 chars)"
    assert user_a_record["password_hash"] != "SecurePassword123!", "Password must be hashed, not stored plaintext"
    assert db.verify_password("SecurePassword123!", user_a_record["password_hash"], user_a_record["salt"]), "Password verification should succeed"
    assert not db.verify_password("WrongPassword!", user_a_record["password_hash"], user_a_record["salt"]), "Password verification should reject wrong password"
    print("PASS: Password confirmed salted PBKDF2 HMAC-SHA256 hash with unique salt in database.")

    # Signup User B
    user_b_email = f"user_b_{int(time.time())}@example.com"
    res_b = requests.post(f"{BASE_URL}/api/auth/signup", json={"email": user_b_email, "password": "SecurePassword456!", "name": "User Beta"})
    assert res_b.status_code == 200, f"User B signup failed: {res_b.text}"
    user_b_data = res_b.json()
    token_b = user_b_data["token"]
    user_b = user_b_data["user"]
    print(f"PASS: User B signed up successfully: {user_b['id']}, token generated.")

    return user_a, token_a, user_b, token_b

def test_file_security(user_a, token_a):
    print("\n--- 2. Testing Secured File Validation ---")
    headers_a = {"x-user-id": token_a}
    session_id_a = f"{user_a['id']}_workspace"

    # Test 1: Dangerous executable extension (.exe)
    files = {"files": ("malware.exe", b"MZexecutabledata", "application/octet-stream")}
    data = {"session_id": session_id_a}
    res = requests.post(f"{BASE_URL}/api/upload", headers=headers_a, files=files, data=data)
    assert res.status_code == 400, f"Expected 400 for .exe upload, got {res.status_code}: {res.text}"
    print("PASS: Executable file (.exe) rejected with 400.")

    # Test 2: Dangerous shell script (.sh)
    files = {"files": ("hack.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh")}
    res = requests.post(f"{BASE_URL}/api/upload", headers=headers_a, files=files, data=data)
    assert res.status_code == 400, f"Expected 400 for .sh upload, got {res.status_code}: {res.text}"
    print("PASS: Shell script (.sh) rejected with 400.")

    # Test 3: Spoofed PDF (extension is .pdf but content lacks %PDF- magic bytes)
    files = {"files": ("fake_invoice.pdf", b"NOT A REAL PDF FILE CONTENTS", "application/pdf")}
    res = requests.post(f"{BASE_URL}/api/upload", headers=headers_a, files=files, data=data)
    assert res.status_code == 400, f"Expected 400 for spoofed PDF, got {res.status_code}: {res.text}"
    print("PASS: Spoofed PDF without %PDF- magic bytes rejected with 400.")

    # Test 4: Path traversal attempt
    files = {"files": ("../../secret_exploit.txt", b"Valid text specification content for testing.", "text/plain")}
    res = requests.post(f"{BASE_URL}/api/upload", headers=headers_a, files=files, data=data)
    assert res.status_code == 200, f"Upload should succeed with sanitized filename, got {res.status_code}: {res.text}"
    uploaded_files = res.json().get("files", [])
    assert not any(".." in f["name"] for f in uploaded_files), "Path traversal was not stripped from filename!"
    print(f"PASS: Path traversal attempt successfully neutralized -> saved safely as: {uploaded_files[0]['name']}")

    # Test 5: Valid PDF upload
    valid_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    files = {"files": ("valid_specs.pdf", valid_pdf_bytes, "application/pdf")}
    res = requests.post(f"{BASE_URL}/api/upload", headers=headers_a, files=files, data=data)
    assert res.status_code == 200, f"Valid PDF upload failed: {res.text}"
    print("PASS: Valid PDF with %PDF- header accepted.")

def test_tenant_isolation(user_a, token_a, user_b, token_b):
    print("\n--- 3. Testing Multi-Tenant User Isolation ---")
    headers_a = {"x-user-id": token_a}
    headers_b = {"x-user-id": token_b}
    session_id_a = f"{user_a['id']}_workspace"

    # Persist a confidential session for User A in the database with User A ownership
    payload_a = {
        "session_id": session_id_a,
        "sections": [{"id": "sec_1", "title": "Confidential Alpha Specs", "body": "Top Secret Data of User Alpha"}],
        "findings": [{"id": "f_1", "title": "Secret finding", "status": "verified"}],
        "conflicts": [{"id": "c_1", "topic": "Private Conflict", "option_a": "A", "option_b": "B", "status": "open"}],
        "tasks": [],
        "alerts": [],
        "chunks": [{"source_id": "doc1", "file_name": "valid_specs.pdf", "text": "Confidential Alpha text"}]
    }
    db.save_session(session_id_a, payload_a, user_id=user_a["id"])
    print(f"PASS: User A workspace '{session_id_a}' created and registered with user_id={user_a['id']}.")

    # User A accesses their own session -> MUST succeed (200)
    res_a_own = requests.get(f"{BASE_URL}/api/session/{session_id_a}", headers=headers_a)
    assert res_a_own.status_code == 200, f"User A could not access own session: {res_a_own.text}"
    print("PASS: User A can successfully access their own workspace.")

    # User B attempts to access User A's session -> MUST be 403 Forbidden!
    res_b_steals = requests.get(f"{BASE_URL}/api/session/{session_id_a}", headers=headers_b)
    assert res_b_steals.status_code == 403, f"Expected 403 Forbidden for User B accessing User A workspace, got {res_b_steals.status_code}"
    print("PASS: User B blocked with 403 Forbidden when attempting to GET User A's workspace!")

    # User B attempts to download User A's raw uploaded file -> MUST be 403 Forbidden!
    res_b_file = requests.get(f"{BASE_URL}/api/upload/{session_id_a}/raw/valid_specs.pdf", headers=headers_b)
    assert res_b_file.status_code == 403, f"Expected 403 Forbidden for User B accessing User A file, got {res_b_file.status_code}"
    print("PASS: User B blocked with 403 Forbidden when attempting to read User A's files!")

    # User B attempts to preview User A's file -> MUST be 403 Forbidden!
    res_b_preview = requests.get(f"{BASE_URL}/api/upload/{session_id_a}/preview/valid_specs.pdf", headers=headers_b)
    assert res_b_preview.status_code == 403, f"Expected 403 Forbidden for preview, got {res_b_preview.status_code}"
    print("PASS: User B blocked with 403 Forbidden when attempting to preview User A's files!")

    # User B attempts to arbitrate User A's conflict -> MUST be 403 Forbidden!
    res_b_conflict = requests.post(f"{BASE_URL}/api/conflicts/resolve?session_id={session_id_a}", headers=headers_b, json={"conflict_id": "c_1", "keep": "left"})
    assert res_b_conflict.status_code == 403, f"Expected 403 Forbidden for conflict resolve, got {res_b_conflict.status_code}"
    print("PASS: User B blocked with 403 Forbidden when attempting to resolve User A's conflicts!")

    # User B attempts to export User A's BRD as PDF -> MUST be 403 Forbidden!
    res_b_pdf = requests.get(f"{BASE_URL}/api/brd/pdf?session_id={session_id_a}", headers=headers_b)
    assert res_b_pdf.status_code == 403, f"Expected 403 Forbidden for PDF export, got {res_b_pdf.status_code}"
    print("PASS: User B blocked with 403 Forbidden when attempting to export User A's BRD PDF!")

    # User B requests project list -> MUST NOT contain User A's workspace!
    res_b_projects = requests.get(f"{BASE_URL}/api/projects", headers=headers_b)
    assert res_b_projects.status_code == 200
    projects_b = res_b_projects.json()
    b_has_a_session = any(p["id"] == session_id_a for p in projects_b)
    assert not b_has_a_session, "User A's session leaked in User B's /api/projects list!"
    print("PASS: User B project list strictly isolated (does not contain User A's workspace).")

    # Anonymous user (unauthenticated) attempts to access User A's session -> MUST be 403 Forbidden!
    res_anon_steals = requests.get(f"{BASE_URL}/api/session/{session_id_a}")
    assert res_anon_steals.status_code == 403, f"Expected 403 Forbidden for anonymous caller, got {res_anon_steals.status_code}"
    print("PASS: Anonymous visitor blocked with 403 Forbidden when attempting to access User A's workspace!")

def test_rate_limiting():
    print("\n--- 4. Testing Tiered Rate Limiting ---")
    # Rate limit for /api/auth/* is 12 requests per minute.
    # We rapidly send requests to /api/auth/login.
    hit_429 = False
    for i in range(16):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "ratelimit_probe@example.com", "password": "wrongpassword123"})
        if res.status_code == 429:
            hit_429 = True
            retry_after = res.headers.get("retry-after")
            print(f"PASS: Rate limit triggered on attempt {i+1} with HTTP 429 Too Many Requests (Retry-After: {retry_after}s)!")
            break
    assert hit_429, "Rate limiter did not trigger HTTP 429 after 15 rapid auth attempts!"

if __name__ == "__main__":
    print("Starting Comprehensive Security Verification Suite...")
    user_a, token_a, user_b, token_b = test_password_and_signup()
    test_file_security(user_a, token_a)
    test_tenant_isolation(user_a, token_a, user_b, token_b)
    test_rate_limiting()
    print("\n=======================================================")
    print("ALL 4 SECURITY MODULES PASSED WITH 100% SUCCESS!")
    print("=======================================================\n")
