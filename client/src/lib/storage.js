/**
 * Encrypted localStorage wrapper using Web Crypto API (AES-GCM, 256-bit).
 *
 * Key derivation:
 *   - Salt: random 16-byte value generated once per device, stored in
 *     localStorage under the key `seelenruh:salt` (not itself encrypted).
 *   - Key material: user ID (stable across sessions) + salt → PBKDF2 → AES-GCM key.
 *   - When no user is logged in, falls back to plain localStorage so pre-auth
 *     state (theme, lang preference) continues to work as before.
 *
 * Migration:
 *   - On first read of an existing key, if decryption fails the raw value is
 *     returned and the key is silently re-written in encrypted form next time it
 *     is set. This lets existing unencrypted sessions continue to work.
 *
 * API mirrors localStorage:
 *   import { secureStorage } from "@/lib/storage";
 *   secureStorage.setItem(key, value);   // value must be JSON-serialisable
 *   secureStorage.getItem(key);          // returns parsed value or null
 *   secureStorage.removeItem(key);
 *   secureStorage.clear(prefix);         // removes all keys with given prefix
 */

const SALT_KEY = "seelenruh:salt";
const ENC_PREFIX = "enc1:"; // version tag prepended to every encrypted blob

let _cachedKey = null;   // CryptoKey — cached for the session
let _userId = null;      // string — set by init()

// ── Internal helpers ───────────────────────────────────────────────────────

function _getOrCreateSalt() {
  let salt = localStorage.getItem(SALT_KEY);
  if (!salt) {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    salt = btoa(String.fromCharCode(...bytes));
    localStorage.setItem(SALT_KEY, salt);
  }
  return salt;
}

function _saltBytes() {
  const b64 = _getOrCreateSalt();
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

async function _deriveKey(userId) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    enc.encode(userId),
    { name: "PBKDF2" },
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: _saltBytes(),
      iterations: 100_000,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

async function _key() {
  if (!_cachedKey || !_userId) return null;
  return _cachedKey;
}

async function _encrypt(plaintext) {
  const key = await _key();
  if (!key) return null;
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = new TextEncoder();
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    enc.encode(plaintext),
  );
  // Encode as: ENC_PREFIX + base64(iv) + "." + base64(ciphertext)
  const ivB64 = btoa(String.fromCharCode(...iv));
  const ctB64 = btoa(String.fromCharCode(...new Uint8Array(ciphertext)));
  return `${ENC_PREFIX}${ivB64}.${ctB64}`;
}

async function _decrypt(stored) {
  if (!stored || !stored.startsWith(ENC_PREFIX)) return null; // not encrypted
  const key = await _key();
  if (!key) return null;
  try {
    const payload = stored.slice(ENC_PREFIX.length);
    const [ivB64, ctB64] = payload.split(".");
    const iv = Uint8Array.from(atob(ivB64), (c) => c.charCodeAt(0));
    const ct = Uint8Array.from(atob(ctB64), (c) => c.charCodeAt(0));
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ct);
    return new TextDecoder().decode(plain);
  } catch {
    return null; // decryption failed — caller falls back to raw
  }
}

// ── Public API ─────────────────────────────────────────────────────────────

/**
 * Call once after the user logs in. Derives and caches the AES key.
 * Must be called before any encrypted setItem/getItem.
 */
export async function initStorage(userId) {
  if (!userId || !crypto?.subtle) return;
  _userId = userId;
  _cachedKey = await _deriveKey(userId);
}

/** Call on logout to discard the in-memory key so future reads get null. */
export function clearStorageKey() {
  _cachedKey = null;
  _userId = null;
}

/** Returns true if the encryption key has been derived and is in memory. */
export function _keyReady() {
  return _cachedKey !== null;
}

export const secureStorage = {
  /**
   * Persist *value* (any JSON-serialisable object) under *key*.
   * Encrypted when a user is logged in; plain otherwise.
   */
  async setItem(key, value) {
    const json = JSON.stringify(value);
    const encrypted = await _encrypt(json);
    localStorage.setItem(key, encrypted ?? json);
  },

  /**
   * Retrieve the value stored under *key*.
   * Handles: encrypted blobs, legacy plain JSON, raw strings.
   * Returns null when the key does not exist.
   */
  async getItem(key) {
    const raw = localStorage.getItem(key);
    if (raw === null) return null;

    // Try decryption first
    if (raw.startsWith(ENC_PREFIX)) {
      const plain = await _decrypt(raw);
      if (plain !== null) {
        try { return JSON.parse(plain); } catch { return plain; }
      }
      // Decryption failed (wrong key / corrupted) — return null to avoid stale data
      return null;
    }

    // Legacy unencrypted value — parse and return as-is
    try { return JSON.parse(raw); } catch { return raw; }
  },

  removeItem(key) {
    localStorage.removeItem(key);
  },

  /** Remove all localStorage entries whose key starts with *prefix*. */
  clear(prefix = "") {
    const toDelete = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(prefix)) toDelete.push(k);
    }
    toDelete.forEach((k) => localStorage.removeItem(k));
  },
};
