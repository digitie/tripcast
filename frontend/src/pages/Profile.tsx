import { FormEvent, useState } from "react";
import { UserApi } from "../api";
import { useAuth } from "../auth";

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const [password, setPassword] = useState("");
  const [chatId, setChatId] = useState(user?.telegram_chat_id ?? "");
  const [enabled, setEnabled] = useState(user?.telegram_enabled ?? true);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setStatus(null);
    setError(null);
    try {
      await UserApi.update({
        password: password || undefined,
        telegram_chat_id: chatId,
        telegram_enabled: enabled,
      });
      setStatus("저장되었습니다.");
      setPassword("");
      await refreshUser();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!user) return null;

  return (
    <div className="container">
      <div className="card">
        <h2>내 정보</h2>
        <div style={{ color: "#6b7280", marginBottom: "1rem" }}>
          {user.email}
        </div>
        <form onSubmit={onSubmit}>
          <div className="form-row">
            <label>새 비밀번호 (변경 시에만 입력)</label>
            <input
              type="password"
              value={password}
              minLength={6}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="form-row">
            <label>텔레그램 chat_id</label>
            <input value={chatId} onChange={(e) => setChatId(e.target.value)} />
          </div>
          <div className="form-row">
            <label>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
              />
              {"  "}텔레그램 알림 사용
            </label>
          </div>
          {error && <div className="error">{error}</div>}
          {status && <div style={{ color: "#16a34a" }}>{status}</div>}
          <button className="primary" type="submit">
            저장
          </button>
        </form>
      </div>
    </div>
  );
}
