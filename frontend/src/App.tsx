import { Link, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Profile from "./pages/Profile";
import Trips from "./pages/Trips";
import TripEditor from "./pages/TripEditor";

function Nav() {
  const { user, logout } = useAuth();
  return (
    <div className="nav">
      <Link to="/">tripcast</Link>
      <div className="spacer" />
      {user ? (
        <>
          <Link to="/trips">내 여행</Link>
          <Link to="/profile">내 정보</Link>
          <button onClick={logout}>로그아웃</button>
        </>
      ) : (
        <>
          <Link to="/login">로그인</Link>
          <Link to="/register">가입</Link>
        </>
      )}
    </div>
  );
}

function Protected({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="container">불러오는 중…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<Navigate to="/trips" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/trips"
          element={
            <Protected>
              <Trips />
            </Protected>
          }
        />
        <Route
          path="/trips/new"
          element={
            <Protected>
              <TripEditor />
            </Protected>
          }
        />
        <Route
          path="/trips/:id"
          element={
            <Protected>
              <TripEditor />
            </Protected>
          }
        />
        <Route
          path="/profile"
          element={
            <Protected>
              <Profile />
            </Protected>
          }
        />
      </Routes>
    </>
  );
}
