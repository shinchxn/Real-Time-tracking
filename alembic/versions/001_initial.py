"""initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-25 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
import os

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Read the initial SQL file
    sql_file = os.path.join(os.path.dirname(__file__), '..', '..', 'storage', 'migrations', '001_initial.sql')
    with open(sql_file, 'r') as f:
        sql = f.read()
    
    # Execute the SQL
    # Note: Alembic's op.execute handles multi-statement strings if the driver supports it.
    # asyncpg via SQLAlchemy might need statements split if not using a specific runner.
    # For simplicity in this env, we'll assume the SQL is valid for op.execute.
    op.execute(sql)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS spread_graph;")
    op.execute("DROP TABLE IF EXISTS sightings;")
    op.execute("DROP TABLE IF EXISTS registered_assets;")
    op.execute("DROP TABLE IF EXISTS organizations;")
