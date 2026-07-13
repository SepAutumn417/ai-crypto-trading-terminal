"""merge v1 migration heads

Revision ID: j1e2f3a4b5c6
Revises: d0e1f2a3b4c5, i2c3d4e5f6a7
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "j1e2f3a4b5c6"
down_revision: tuple[str, str] = ("d0e1f2a3b4c5", "i2c3d4e5f6a7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This revision only joins two already-applied schema branches.
    pass


def downgrade() -> None:
    # Alembic can return to either parent branch without schema changes here.
    pass
