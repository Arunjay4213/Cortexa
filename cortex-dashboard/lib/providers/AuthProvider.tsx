"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { API_BASE, setApiKey, clearApiKey } from "@/lib/api/client";

interface KeyInfo {
  key_id: string;
  name: string;
  key_prefix: string;
}

interface AuthContextValue {
  isAuthenticated: boolean;
  keyInfo: KeyInfo | null;
  login: (apiKey: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  isAuthenticated: false,
  keyInfo: null,
  login: async () => {},
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const COOKIE_NAME = "cortex_api_key";

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${60 * 60 * 24 * 90}; SameSite=Lax`;
}

function deleteCookie(name: string) {
  document.cookie = `${name}=; path=/; max-age=0`;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [keyInfo, setKeyInfo] = useState<KeyInfo | null>(null);
  const [checked, setChecked] = useState(false);

  const validate = useCallback(async (apiKey: string): Promise<KeyInfo> => {
    const res = await fetch(`${API_BASE}/v1/auth/validate`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!res.ok) {
      throw new Error("Invalid API key");
    }
    return res.json();
  }, []);

  // Restore session from cookie on mount
  useEffect(() => {
    const stored = getCookie(COOKIE_NAME);
    if (!stored) {
      setChecked(true);
      return;
    }

    setApiKey(stored);
    validate(stored)
      .then((info) => setKeyInfo(info))
      .catch(() => {
        clearApiKey();
        deleteCookie(COOKIE_NAME);
      })
      .finally(() => setChecked(true));
  }, [validate]);

  const login = useCallback(
    async (apiKey: string) => {
      const info = await validate(apiKey);
      setApiKey(apiKey);
      setCookie(COOKIE_NAME, apiKey);
      setKeyInfo(info);
    },
    [validate]
  );

  const logout = useCallback(() => {
    clearApiKey();
    deleteCookie(COOKIE_NAME);
    setKeyInfo(null);
  }, []);

  // Don't render children until we've checked the cookie
  if (!checked) {
    return null;
  }

  return (
    <AuthContext.Provider
      value={{ isAuthenticated: keyInfo !== null, keyInfo, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}
