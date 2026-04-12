"""init schema

Revision ID: 0001_init
Revises:
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
        sa.Column("telegram_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "trips",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
        sa.Column("telegram_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notify_lead_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trips_user_id", "trips", ["user_id"])

    op.create_table(
        "trip_places",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_date", sa.Date, nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sido", sa.String(40), nullable=False),
        sa.Column("sigungu", sa.String(60), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("nx", sa.Integer, nullable=True),
        sa.Column("ny", sa.Integer, nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=True),
    )
    op.create_index("ix_trip_places_trip_id", "trip_places", ["trip_id"])

    op.create_table(
        "rest_stops",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("external_code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("route_name", sa.String(100), nullable=True),
        sa.Column("direction", sa.String(50), nullable=True),
        sa.Column("sido", sa.String(40), nullable=True),
        sa.Column("sigungu", sa.String(60), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("raw", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rest_stop_weather",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("rest_stop_id", sa.Integer, sa.ForeignKey("rest_stops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("humidity", sa.Float, nullable=True),
        sa.Column("wind_speed", sa.Float, nullable=True),
        sa.Column("precipitation", sa.Float, nullable=True),
        sa.Column("sky", sa.String(50), nullable=True),
        sa.Column("raw", sa.JSON, nullable=True),
        sa.UniqueConstraint("rest_stop_id", "observed_at", name="uq_rest_stop_obs"),
    )
    op.create_index("ix_rest_stop_weather_rest_stop_id", "rest_stop_weather", ["rest_stop_id"])

    op.create_table(
        "weather_forecasts",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("nx", sa.Integer, nullable=False),
        sa.Column("ny", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("base_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forecast_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("sky", sa.String(20), nullable=True),
        sa.Column("pty", sa.String(20), nullable=True),
        sa.Column("precipitation", sa.Float, nullable=True),
        sa.Column("humidity", sa.Float, nullable=True),
        sa.Column("wind_speed", sa.Float, nullable=True),
        sa.Column("raw", sa.JSON, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("nx", "ny", "forecast_at", "kind", name="uq_fcst_grid_time"),
    )
    op.create_index("ix_weather_forecasts_grid", "weather_forecasts", ["nx", "ny"])

    op.create_table(
        "fuel_stations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("external_code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("sido", sa.String(40), nullable=True),
        sa.Column("sigungu", sa.String(60), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("raw", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "fuel_prices",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("station_id", sa.Integer, sa.ForeignKey("fuel_stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gasoline", sa.Float, nullable=True),
        sa.Column("premium_gasoline", sa.Float, nullable=True),
        sa.Column("diesel", sa.Float, nullable=True),
        sa.Column("raw", sa.JSON, nullable=True),
        sa.UniqueConstraint("station_id", "observed_at", name="uq_station_obs"),
    )
    op.create_index("ix_fuel_prices_station_id", "fuel_prices", ["station_id"])

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("trip_id", sa.Integer, sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("target_date", sa.Date, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("error", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
    op.drop_table("fuel_prices")
    op.drop_table("fuel_stations")
    op.drop_table("weather_forecasts")
    op.drop_table("rest_stop_weather")
    op.drop_table("rest_stops")
    op.drop_table("trip_places")
    op.drop_table("trips")
    op.drop_table("users")
