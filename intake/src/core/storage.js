// localStorage draft persistence. Never writes File objects or bytes:
// callers must pass the output of draftSnapshot().

export function loadDraft(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

export function saveDraft(key, snapshot) {
  try {
    localStorage.setItem(key, JSON.stringify(snapshot));
  } catch (_) {
    // Quota/availability failures are best-effort; submission still works.
  }
}

export function clearDraft(key) {
  try {
    localStorage.removeItem(key);
  } catch (_) {
    // ignore
  }
}
