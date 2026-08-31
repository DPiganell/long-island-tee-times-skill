// Thin IndexedDB wrapper. Two stores: sessions (practice data) and prefs (key/value).

const DB_NAME = 'golf-practice';
const DB_VERSION = 1;

let dbPromise = null;

function openDB() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('sessions')) {
        const s = db.createObjectStore('sessions', { keyPath: 'id' });
        s.createIndex('startedAt', 'startedAt');
      }
      if (!db.objectStoreNames.contains('prefs')) {
        db.createObjectStore('prefs', { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

function tx(db, store, mode, fn) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const s = t.objectStore(store);
    let result;
    try {
      result = fn(s);
    } catch (e) {
      reject(e);
      return;
    }
    t.oncomplete = () => {
      if (result && typeof result.then === 'function') result.then(resolve, reject);
      else if (result && 'result' in result) resolve(result.result);
      else resolve(result);
    };
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error || new Error('transaction aborted'));
  });
}

export async function putSession(session) {
  const db = await openDB();
  return tx(db, 'sessions', 'readwrite', (s) => s.put(session));
}

export async function getSession(id) {
  const db = await openDB();
  return tx(db, 'sessions', 'readonly', (s) => s.get(id));
}

export async function deleteSession(id) {
  const db = await openDB();
  return tx(db, 'sessions', 'readwrite', (s) => s.delete(id));
}

// All sessions, newest first.
export async function getAllSessions() {
  const db = await openDB();
  const all = await tx(db, 'sessions', 'readonly', (s) => s.getAll());
  return (all || []).sort((a, b) => (a.startedAt < b.startedAt ? 1 : -1));
}

export async function getActiveSession() {
  const all = await getAllSessions();
  return all.find((s) => s.status === 'active') || null;
}

export async function getPref(key, fallback = null) {
  const db = await openDB();
  const row = await tx(db, 'prefs', 'readonly', (s) => s.get(key));
  return row ? row.value : fallback;
}

export async function setPref(key, value) {
  const db = await openDB();
  return tx(db, 'prefs', 'readwrite', (s) => s.put({ key, value }));
}

// Ask the browser to protect this origin's storage from eviction.
export function requestPersistence() {
  if (navigator.storage && navigator.storage.persist) {
    navigator.storage.persist().catch(() => {});
  }
}
