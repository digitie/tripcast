import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Trip, TripApi } from "../api";

export default function Trips() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setTrips(await TripApi.list());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onDelete(id: number) {
    if (!confirm("삭제할까요?")) return;
    await TripApi.remove(id);
    refresh();
  }

  return (
    <div className="container">
      <div style={{ display: "flex", alignItems: "center", marginBottom: "1rem" }}>
        <h2 style={{ margin: 0, flex: 1 }}>내 여행 계획</h2>
        <Link to="/trips/new">
          <button className="primary">+ 새 여행</button>
        </Link>
      </div>
      {loading && <div>불러오는 중…</div>}
      {error && <div className="error">{error}</div>}
      {!loading && trips.length === 0 && (
        <div className="card">등록된 여행이 없습니다.</div>
      )}
      {trips.map((t) => (
        <div className="card" key={t.id}>
          <div style={{ display: "flex", alignItems: "center" }}>
            <div style={{ flex: 1 }}>
              <h3 style={{ margin: "0 0 0.25rem" }}>{t.title}</h3>
              <div style={{ color: "#6b7280" }}>
                {t.start_date} ~ {t.end_date} · 알림 {t.notify_lead_days}일 전부터
              </div>
            </div>
            <Link to={`/trips/${t.id}`}>
              <button>수정</button>
            </Link>
            <button style={{ marginLeft: 8 }} onClick={() => onDelete(t.id)}>
              삭제
            </button>
          </div>
          <ul style={{ marginTop: "0.75rem" }}>
            {t.places.map((p) => (
              <li key={p.id}>
                {p.visit_date} · {p.sido} {p.sigungu}
                {p.name ? ` · ${p.name}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
