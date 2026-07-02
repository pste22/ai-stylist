import { useState, useEffect } from "react";

const USER_ID_KEY = "mira_user_id";
const USER_NAME_KEY = "mira_user_name";

function generateId() {
  return crypto.randomUUID();
}

// Returns { userId, userName, setUserName, isNewUser }
// userId is a stable UUID in localStorage.
// userName is null until the user provides it (first visit).
export function useUserIdentity() {
  const [userId] = useState(() => {
    const existing = localStorage.getItem(USER_ID_KEY);
    if (existing) return existing;
    const id = generateId();
    localStorage.setItem(USER_ID_KEY, id);
    return id;
  });

  const [userName, setUserNameState] = useState(
    () => localStorage.getItem(USER_NAME_KEY) || null
  );

  const isNewUser = !userName;

  function setUserName(name) {
    const trimmed = name.trim();
    if (!trimmed) return;
    localStorage.setItem(USER_NAME_KEY, trimmed);
    setUserNameState(trimmed);
  }

  return { userId, userName, setUserName, isNewUser };
}
