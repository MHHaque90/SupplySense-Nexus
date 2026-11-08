"""Phase 11 AI Decision Copilot: user API keys + AI tables.

Revision ID: phase11_ai_copilot
Revises: initial
Create Date: 2026-10-04 00:00:00.000000

One migration, three concerns: ``users.api_key_hash``, ``ai_conversations``
+ ``ai_messages`` (PostgreSQL-backed chat history), and ``ai_approvals``
(declarative human-decision records; never an execution path).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'phase11_ai_copilot'
down_revision: Union[str, Sequence[str], None] = 'initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- C1: per-user opaque API key hash (SHA-256 hex, 64 chars). ---
    op.add_column('users', sa.Column('api_key_hash', sa.String(64), nullable=True))
    op.create_index(
        'ix_users_api_key_hash', 'users', ['api_key_hash'], unique=True
    )

    # --- C4: PostgreSQL-backed conversation history. ---
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('last_intent', sa.String(50), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )

    op.create_table(
        'ai_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('ai_conversations.id'), nullable=False, index=True),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(50), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('tool_calls', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )

    # --- C1/C4: declared actions awaiting human decisions (no execution). ---
    op.create_table(
        'ai_approvals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('ai_conversations.id'), nullable=False, index=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('requested_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('declaration', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', index=True),
        sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('decided_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('decision_comment', sa.Text(), nullable=True),
        sa.Column('data_source_label', sa.String(20), nullable=False, server_default='synthetic'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False, onupdate=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('ai_approvals')
    op.drop_table('ai_messages')
    op.drop_table('ai_conversations')
    op.drop_index('ix_users_api_key_hash', table_name='users')
    op.drop_column('users', 'api_key_hash')
