import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Trip, TripApi, TripPlace } from "../api";

type Draft = Omit<Trip, "id" | "created_at">;

const empty: Draft = {
  title: "",
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  telegram_chat_id: null,
  telegram_enabled: true,
  notify_lead_days: 7,
  places: [],
};

export default function TripEditor() {
  const { id } = useParams();
  const nav = useNavigate();
  const isEdit = Boolean(id);
  const [trip, setTrip] = useState<Draft>(empty);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      TripApi.get(Number(id))
        .then((t) => {
          const { id: _id, created_at: _c, ...rest } = t;
          setTrip(rest);
        })
        .catch((e) => setError((e as Error).message));
    }
  }, [id]);

  function updatePlace(idx: number, patch: Partial<TripPlace>) {
    setTrip((prev) => {
      const places = [...prev.places];
      places[idx] = { ...places[idx], ...patch };
      return { ...prev, places };
    });
  }

  function addPlace() {
    setTrip((prev) => ({
      ...prev,
      places: [
        ...prev.places,
        {
          visit_date: prev.start_date,
          order_index: prev.places.length,
          sido: "",
          sigungu: "",
          name: "",
        },
      ],
    }));
  }

  function removePlace(idx: number) {
    setTrip((prev) => ({
      ...prev,
      places: prev.places.filter((_, i) => i !== idx),
    }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (isEdit) {
        await TripApi.update(Number(id), trip);
      } else {
        await TripApi.create(trip);
      }
      nav("/trips");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h2>{isEdit ? "여행 수정" : "새 여행"}</h2>
        <form onSubmit={onSubmit}>
          <div className="form-row">
            <label>여행 이름</label>
            <input
              value={trip.title}
              onChange={(e) => setTrip({ ...trip, title: e.target.value })}
              required
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
            <div className="form-row">
              <label>시작일</label>
              <input
                type="date"
                value={trip.start_date}
                onChange={(e) => setTrip({ ...trip, start_date: e.target.value })}
                required
              />
            </div>
            <div className="form-row">
              <label>종료일</label>
              <input
                type="date"
                value={trip.end_date}
                onChange={(e) => setTrip({ ...trip, end_date: e.target.value })}
                required
              />
            </div>
            <div className="form-row">
              <label>알림 시작 (N일 전)</label>
              <input
                type="number"
                min={1}
                max={14}
                value={trip.notify_lead_days}
                onChange={(e) =>
                  setTrip({ ...trip, notify_lead_days: Number(e.target.value) })
                }
              />
            </div>
          </div>

          <div className="form-row">
            <label>이 여행만의 텔레그램 chat_id (비우면 내 정보 기본값 사용)</label>
            <input
              value={trip.telegram_chat_id ?? ""}
              onChange={(e) =>
                setTrip({ ...trip, telegram_chat_id: e.target.value || null })
              }
            />
          </div>
          <div className="form-row">
            <label>
              <input
                type="checkbox"
                checked={trip.telegram_enabled}
                onChange={(e) =>
                  setTrip({ ...trip, telegram_enabled: e.target.checked })
                }
              />
              {"  "}텔레그램 알림 사용
            </label>
          </div>

          <h3>날짜별 장소 (시군구)</h3>
          {trip.places.map((p, idx) => (
            <div className="place-row" key={idx}>
              <div>
                <label>날짜</label>
                <input
                  type="date"
                  value={p.visit_date}
                  onChange={(e) => updatePlace(idx, { visit_date: e.target.value })}
                />
              </div>
              <div>
                <label>시/도</label>
                <input
                  value={p.sido}
                  onChange={(e) => updatePlace(idx, { sido: e.target.value })}
                  placeholder="예: 강원특별자치도"
                />
              </div>
              <div>
                <label>시/군/구</label>
                <input
                  value={p.sigungu}
                  onChange={(e) => updatePlace(idx, { sigungu: e.target.value })}
                  placeholder="예: 강릉시"
                />
              </div>
              <div>
                <label>상세 장소 (선택)</label>
                <input
                  value={p.name ?? ""}
                  onChange={(e) => updatePlace(idx, { name: e.target.value })}
                />
              </div>
              <button type="button" onClick={() => removePlace(idx)}>
                삭제
              </button>
            </div>
          ))}
          <button type="button" onClick={addPlace}>
            + 장소 추가
          </button>

          {error && <div className="error">{error}</div>}
          <div style={{ marginTop: "1rem" }}>
            <button className="primary" type="submit">
              저장
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
