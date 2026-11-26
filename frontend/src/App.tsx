import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AuthPage from "./pages/AuthPage";
import DocumentsPage from "./pages/DocumentsPage";
import ChatPage from "./pages/ChatPage";
import { auth } from "./api/client";

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null); // null = checking

  useEffect(() => {
    auth.me()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false));
  }, []);

  if (authed === null) return null; // silent initial check

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/auth"
          element={
            authed ? <Navigate to="/" replace /> : <AuthPage onAuth={() => setAuthed(true)} />
          }
        />
        <Route
          path="/"
          element={
            authed ? (
              <DocumentsPage onLogout={() => setAuthed(false)} />
            ) : (
              <Navigate to="/auth" replace />
            )
          }
        />
        <Route
          path="/documents/:documentId"
          element={authed ? <ChatPage /> : <Navigate to="/auth" replace />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
