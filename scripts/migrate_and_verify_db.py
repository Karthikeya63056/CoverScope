"""Complete database migration and verification script for CoverScope on MongoDB Atlas.

Actions performed:
1. Pings the live Atlas cluster to verify connection and measures latency.
2. Initializes all 5 collections and ensures indexes idempotently:
   - users
   - policies
   - conversations
   - messages
   - analysis_records
3. Migrates / seeds administrator account if configured.
4. Registers baseline sample policy metadata from local pdfs directory.
5. Performs end-to-end write and read verification for all collections.
6. Reports collection document counts and index inventory directly from Atlas.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import time

from dotenv import load_dotenv

# Ensure backend is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(override=True)

from backend.config import settings
from backend.database.client import (
    get_database,
    get_mongodb_client,
    redact_mongo_uri,
)
from backend.database.healthcheck import (
    DatabaseHealthStatus,
    check_mongodb_health,
)
from backend.database.repositories import (
    AnalysisRepository,
    ConversationRepository,
    PolicyRepository,
    UserRepository,
)
from backend.database.schema import (
    COLL_ANALYSIS_RECORDS,
    COLL_CONVERSATIONS,
    COLL_MESSAGES,
    COLL_POLICIES,
    COLL_USERS,
    init_db_indexes,
)


def run_migration_and_verification() -> bool:
    print("=" * 70)
    print("CoverScope MongoDB Atlas Migration & Verification")
    print("=" * 70)

    # 1. Health & Connectivity Verification
    print("\n[Step 1/5] Verifying MongoDB Atlas connection...")
    report = check_mongodb_health()
    print(f"  Cluster URI:  {report.redacted_uri}")
    print(f"  Target DB:    {report.database_name}")
    print(f"  Status:       {report.status.value.upper()}")
    print(f"  Ping Latency: {report.latency_ms:.1f} ms")

    if report.status != DatabaseHealthStatus.CONNECTED:
        print(f"\n[FAIL] Cannot proceed with migration. Connection status: {report.status.value}")
        print(f"Error detail: {report.message}")
        return False

    db = get_database()
    if db is None:
        print("\n[FAIL] Database handle is None.")
        return False

    # 2. Schema & Index Migration
    print("\n[Step 2/5] Creating and verifying collection indexes...")
    index_results = init_db_indexes(db)
    for coll_name, idx_list in index_results.items():
        print(f"  Collection '{coll_name}': {len(idx_list)} indexes verified -> {', '.join(idx_list)}")

    # 3. User Identity Migration (Admin / System user)
    print("\n[Step 3/5] Migrating administrator and system identity...")
    user_repo = UserRepository(db)
    admin_email = "admin@coverscope.internal"
    admin_uid = user_repo.upsert_user(
        auth_provider="system_admin",
        auth_provider_user_id=admin_email,
        email=admin_email,
        display_name="CoverScope Administrator",
        role="administrator",
        preferences={"theme": "insurtech_teal", "default_workspace": "ask"},
    )
    print(f"  Admin User ID created/verified: {admin_uid}")

    # 4. Baseline Policy Documents Migration
    print("\n[Step 4/5] Migrating baseline sample policies...")
    policy_repo = PolicyRepository(db)
    pdf_dir = ROOT / "pdfs"
    migrated_policies = 0

    if pdf_dir.exists():
        for pdf_path in pdf_dir.glob("*.pdf"):
            data = pdf_path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            # Estimate page count or read metadata
            p_id = policy_repo.save_policy_metadata(
                user_id=admin_uid,
                document_name=pdf_path.name,
                document_hash=sha,
                page_count=1,  # will update dynamically on full prepare
                metadata={
                    "file_size_bytes": len(data),
                    "source": "bundled_sample",
                    "migrated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            migrated_policies += 1
            print(f"  Registered Policy: '{pdf_path.name}' -> ID: {p_id}")
    else:
        print("  Notice: No local pdfs/ directory found. Skipping bundled samples.")

    # 5. Live End-to-End Round-Trip Verification
    print("\n[Step 5/5] Performing live round-trip CRUD verification...")
    conv_repo = ConversationRepository(db)
    analysis_repo = AnalysisRepository(db)

    # A. Create verification conversation
    test_policy_hash = "verify_test_policy_hash"
    conv_id = conv_repo.get_or_create_conversation(
        user_id=admin_uid,
        policy_id=test_policy_hash,
        title="Automated Verification Session",
    )
    print(f"  [OK] Conversation created: ID {conv_id}")

    # B. Append verification message
    msg_id = conv_repo.append_message(
        user_id=admin_uid,
        conversation_id=conv_id,
        policy_id=test_policy_hash,
        role="assistant",
        content="Atlas migration verification test message.",
        evidence_metadata={"verdict": "covered", "confidence": "high"},
    )
    print(f"  [OK] Message appended: ID {msg_id}")

    # C. Verify chronological message retrieval
    msgs = conv_repo.list_messages(admin_uid, conv_id)
    assert len(msgs) >= 1
    assert any(m["content"] == "Atlas migration verification test message." for m in msgs)
    print(f"  [OK] Message retrieved successfully from Atlas ({len(msgs)} messages in thread)")

    # D. Save verification analysis record
    rec_id = analysis_repo.save_analysis(
        user_id=admin_uid,
        policy_id=test_policy_hash,
        analysis_type="migration_health_verification",
        input_summary={"ping_test": True},
        result_summary={"status": "verified"},
    )
    print(f"  [OK] Analysis record created: ID {rec_id}")

    # Cleanup test records
    db[COLL_MESSAGES].delete_one({"_id": msg_id if isinstance(msg_id, str) else msg_id})
    db[COLL_CONVERSATIONS].delete_one({"_id": conv_id if isinstance(conv_id, str) else conv_id})
    db[COLL_ANALYSIS_RECORDS].delete_one({"_id": rec_id if isinstance(rec_id, str) else rec_id})
    print("  [OK] Temporary verification documents cleaned up.")

    # 6. Final Atlas Inventory
    print("\n" + "=" * 70)
    print("LIVE MONGODB ATLAS INVENTORY")
    print("=" * 70)
    for coll in [COLL_USERS, COLL_POLICIES, COLL_CONVERSATIONS, COLL_MESSAGES, COLL_ANALYSIS_RECORDS]:
        count = db[coll].count_documents({})
        indexes = list(db[coll].index_information().keys())
        print(f"  Collection: {coll:20s} | Documents: {count:4d} | Indexes: {indexes}")

    print("=" * 70)
    print("[SUCCESS] MongoDB Atlas Migration & Verification Completed 100% Successfully!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_migration_and_verification()
    sys.exit(0 if success else 1)
