from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Trip, TripPlace, User
from ..schemas import TripCreate, TripOut, TripPlaceIn, TripPlaceOut, TripUpdate
from ..services.region import latlon_to_grid, sigungu_to_latlon

router = APIRouter(prefix="/trips", tags=["trips"])


def _place_to_out(place: TripPlace) -> TripPlaceOut:
    lat: float | None = None
    lon: float | None = None
    if place.location is not None:
        pt = to_shape(place.location)
        lat, lon = pt.y, pt.x
    return TripPlaceOut(
        id=place.id,
        visit_date=place.visit_date,
        order_index=place.order_index,
        sido=place.sido,
        sigungu=place.sigungu,
        name=place.name,
        nx=place.nx,
        ny=place.ny,
        latitude=lat,
        longitude=lon,
        radius_m=place.radius_m,
    )


def _trip_to_out(trip: Trip) -> TripOut:
    return TripOut(
        id=trip.id,
        title=trip.title,
        start_date=trip.start_date,
        end_date=trip.end_date,
        telegram_chat_id=trip.telegram_chat_id,
        telegram_enabled=trip.telegram_enabled,
        notify_lead_days=trip.notify_lead_days,
        places=[_place_to_out(p) for p in trip.places],
        created_at=trip.created_at,
    )


def _build_place(payload: TripPlaceIn) -> TripPlace:
    lat, lon = payload.latitude, payload.longitude
    if lat is None or lon is None:
        coord = sigungu_to_latlon(payload.sido, payload.sigungu)
        if coord is not None:
            lat, lon = coord
    nx = ny = None
    location = None
    if lat is not None and lon is not None:
        grid = latlon_to_grid(lat, lon)
        nx, ny = grid.nx, grid.ny
        location = from_shape(Point(lon, lat), srid=4326)
    return TripPlace(
        visit_date=payload.visit_date,
        order_index=payload.order_index,
        sido=payload.sido,
        sigungu=payload.sigungu,
        name=payload.name,
        nx=nx,
        ny=ny,
        location=location,
        radius_m=payload.radius_m,
    )


@router.get("", response_model=list[TripOut])
def list_trips(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TripOut]:
    rows = db.scalars(
        select(Trip)
        .where(Trip.user_id == current.id)
        .options(selectinload(Trip.places))
        .order_by(Trip.start_date.desc())
    ).all()
    return [_trip_to_out(t) for t in rows]


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripOut:
    if payload.end_date < payload.start_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="end_date must be >= start_date")
    trip = Trip(
        user_id=current.id,
        title=payload.title,
        start_date=payload.start_date,
        end_date=payload.end_date,
        telegram_chat_id=payload.telegram_chat_id or current.telegram_chat_id,
        telegram_enabled=payload.telegram_enabled,
        notify_lead_days=payload.notify_lead_days,
        places=[_build_place(p) for p in payload.places],
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return _trip_to_out(trip)


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(
    trip_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripOut:
    trip = db.scalar(
        select(Trip)
        .where(Trip.id == trip_id, Trip.user_id == current.id)
        .options(selectinload(Trip.places))
    )
    if not trip:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return _trip_to_out(trip)


@router.patch("/{trip_id}", response_model=TripOut)
def update_trip(
    trip_id: int,
    payload: TripUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripOut:
    trip = db.scalar(
        select(Trip)
        .where(Trip.id == trip_id, Trip.user_id == current.id)
        .options(selectinload(Trip.places))
    )
    if not trip:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    if payload.title is not None:
        trip.title = payload.title
    if payload.start_date is not None:
        trip.start_date = payload.start_date
    if payload.end_date is not None:
        trip.end_date = payload.end_date
    if payload.telegram_chat_id is not None:
        trip.telegram_chat_id = payload.telegram_chat_id
    if payload.telegram_enabled is not None:
        trip.telegram_enabled = payload.telegram_enabled
    if payload.notify_lead_days is not None:
        trip.notify_lead_days = payload.notify_lead_days

    if payload.places is not None:
        trip.places.clear()
        db.flush()
        for p in payload.places:
            trip.places.append(_build_place(p))

    if trip.end_date < trip.start_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="end_date must be >= start_date")

    db.commit()
    db.refresh(trip)
    return _trip_to_out(trip)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.user_id == current.id))
    if not trip:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    db.delete(trip)
    db.commit()
