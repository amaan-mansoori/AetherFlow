"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api/client";
import type { User } from "@/types/api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "unavailable";

interface AuthValue {
  status: AuthStatus;
  user: User | null;
  signIn(email: string, password: string): Promise<void>;
  signOut(): Promise<void>;
  retrySession(): Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);

  const restoreSession = useCallback(async () => {
    try {
      const session = await api.refreshSession();
      setUser(session.user);
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof TypeError) {
        setStatus("unavailable");
      } else {
        setUser(null);
        setStatus("unauthenticated");
      }
    }
  }, []);

  const retrySession = useCallback(async () => {
    setStatus("loading");
    await restoreSession();
  }, [restoreSession]);

  useEffect(() => {
    const unsubscribe = api.subscribe((token, sessionUser) => {
      if (token && sessionUser) {
        setUser(sessionUser);
        setStatus("authenticated");
      } else {
        setUser(null);
        setStatus("unauthenticated");
      }
    });
    // Session updates occur after the cookie refresh request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void restoreSession();
    return unsubscribe;
  }, [restoreSession]);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    api.setSession(result);
    setUser(result.user);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo(
    () => ({ status, user, signIn, signOut, retrySession }),
    [status, user, signIn, signOut, retrySession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
