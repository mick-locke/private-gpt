"""make username

Revision ID: bb09ed1e141b
Revises: bca1465a100f
Create Date: 2024-01-28 11:48:31.406920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb09ed1e141b'
down_revision: Union[str, None] = 'bca1465a100f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    # op.create_unique_constraint('unique_user_role', 'user_roles', ['user_id', 'role_id', 'company_id'])
    op.create_unique_constraint('unique_username_no_spacing', 'users', ['fullname'])
    op.create_unique_constraint(None, 'users', ['fullname'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_constraint('unique_username_no_spacing', 'users', type_='unique')
    # op.drop_constraint('unique_user_role', 'user_roles', type_='unique')
    # ### end Alembic commands ###
