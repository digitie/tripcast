"""sigungu regions + per-place radius

Revision ID: 0002_region_boundaries
Revises: 0001_init
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography, Geometry


revision = "0002_region_boundaries"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 날짜별 장소 반경 (기본 10km)
    op.add_column(
        "trip_places",
        sa.Column("radius_m", sa.Integer, nullable=False, server_default="10000"),
    )

    # 시군구 경계
    op.create_table(
        "sigungu_regions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("sido", sa.String(40), nullable=False),
        sa.Column("sigungu", sa.String(80), nullable=False),
        sa.Column("center_lat", sa.Float, nullable=True),
        sa.Column("center_lon", sa.Float, nullable=True),
        sa.Column("center", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("nx", sa.Integer, nullable=True),
        sa.Column("ny", sa.Integer, nullable=True),
        sa.Column(
            "geom",
            Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_sigungu_regions_sido_sigungu", "sigungu_regions", ["sido", "sigungu"]
    )


def downgrade() -> None:
    op.drop_index("ix_sigungu_regions_sido_sigungu", table_name="sigungu_regions")
    op.drop_table("sigungu_regions")
    op.drop_column("trip_places", "radius_m")
