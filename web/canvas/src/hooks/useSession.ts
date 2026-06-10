import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

export function useSession() {
  const [sessionId, setSessionId] = useState<string>(() => {
    const stored = localStorage.getItem('chatbiz-session-id');
    if (stored) return stored;
    const newId = uuidv4();
    localStorage.setItem('chatbiz-session-id', newId);
    return newId;
  });

  useEffect(() => {
    // Sync sessionId to URL hash for cross-tab sharing
    if (window.location.hash !== `#session=${sessionId}`) {
      window.location.hash = `session=${sessionId}`;
    }
  }, [sessionId]);

  const newSession = () => {
    const newId = uuidv4();
    localStorage.setItem('chatbiz-session-id', newId);
    setSessionId(newId);
  };

  return { sessionId, newSession };
}
