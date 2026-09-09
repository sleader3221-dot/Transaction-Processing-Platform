"""Initial schema

Revision ID: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("uq_api_keys_client_id", "api_keys", ["client_id"], unique=True)

    op.create_table(
        "imports",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("status", sa.Enum("QUEUED", "PROCESSING", "COMPLETED", "FAILED",
                                     name="import_status"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(2048), nullable=True),
        sa.Column("client_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_imports_status", "imports", ["status"])

    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("transaction_id", sa.String(255), nullable=False),
        sa.Column("account_id", sa.String(255), nullable=False),
        sa.Column("type", sa.Enum("CREDIT", "DEBIT", name="transaction_type"),
                  nullable=False),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("import_id", sa.String(26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("uq_transactions_txn_id", "transactions", ["transaction_id"], unique=True)
    op.create_index("ix_txn_account_timestamp", "transactions", ["account_id", "timestamp"])
    op.create_index("ix_txn_account_type", "transactions", ["account_id", "type"])
    op.create_index("ix_txn_currency", "transactions", ["currency"])
    op.create_index("ix_txn_timestamp", "transactions", ["timestamp"])
    op.create_index("ix_txn_import_id", "transactions", ["import_id"])

    op.create_table(
        "import_errors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("import_id", sa.String(26),
                  sa.ForeignKey("imports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(255), nullable=True),
        sa.Column("error", sa.String(2048), nullable=False),
    )
    op.create_index("ix_import_errors_import_id", "import_errors", ["import_id"])


def downgrade():
    op.drop_table("import_errors")
    op.drop_table("transactions")
    op.drop_table("imports")
    op.drop_table("api_keys")
    op.execute("DROP TYPE IF EXISTS import_status")
    op.execute("DROP TYPE IF EXISTS transaction_type")