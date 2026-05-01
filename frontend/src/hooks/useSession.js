import { useState, useEffect } from "react";
import { createSession } from "../api/client.js";

const STORAGE_KEY = "ace_session_id";

export function useSession() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(STORAGE_KEY));
  const [loading, setLoading] = useState(!sessionId);

  useEffect(() => {
    if (sessionId) return;
    let cancelled = false;
    createSession()
      .then((data) => {
        if (cancelled) return;
        localStorage.setItem(STORAGE_KEY, data.session_id);
        setSessionId(data.session_id);
        setLoading(false);
      })
      .catch(() => setLoading(false));
    return () => { cancelled = true; };
  }, []);

  function clearSession() {
    localStorage.removeItem(STORAGE_KEY);
    setSessionId(null);
    setLoading(true);
  }

  return { sessionId, loading, clearSession };
}
