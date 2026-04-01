import sqlalchemy as sa

metadata = sa.MetaData()

verification_logs = sa.Table(
    "verification_logs",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("response_text", sa.Text, nullable=False),
    sa.Column("sources_hash", sa.Text, nullable=False),
    sa.Column("hallucination_index", sa.Float, nullable=False),
    sa.Column("total_claims", sa.Integer, nullable=False),
    sa.Column("grounded_count", sa.Integer, nullable=False),
    sa.Column("hallucinated_count", sa.Integer, nullable=False),
    sa.Column("claims", sa.JSON, nullable=False),
    sa.Column("latency_ms", sa.Float, nullable=False),
    sa.Column("api_key_id", sa.Text, nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    ),
)

api_keys = sa.Table(
    "api_keys",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("key_hash", sa.Text, nullable=False, unique=True),
    sa.Column("key_prefix", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("rate_limit_rpm", sa.Integer, default=60),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    ),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
)
