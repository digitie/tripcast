import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [chatId, setChatId] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await register({
        email,
        password,
        telegram_chat_id: chatId || undefined,
        telegram_enabled: enabled,
      });
      nav("/trips");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h2>회원가입</h2>
        <form onSubmit={onSubmit}>
          <div className="form-row">
            <label>이메일 (아이디)</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-row">
            <label>비밀번호 (6자 이상)</label>
            <input
              type="password"
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div className="form-row">
            <label>텔레그램 chat_id (기본값, 나중에 변경 가능)</label>
            <input value={chatId} onChange={(e) => setChatId(e.target.value)} />
          </div>
          <div className="form-row">
            <label>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
              />
              {"  "}텔레그램 알림 기본 사용
            </label>
          </div>
          {error && <div className="error">{error}</div>}
          <button className="primary" type="submit">
            가입
          </button>
        </form>
      </div>
    </div>
  );
}
