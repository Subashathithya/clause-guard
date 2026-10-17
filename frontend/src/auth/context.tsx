import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { User } from '../types';
import { AUTH_EXPIRED_EVENT, api, tokenStore } from '../api';

interface AuthContextValue {
  user: User | null;
  booting: boolean;
  loggedIn: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (email: string, password: string, fullName: string) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);

  const clearSession = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
  }, []);

  const restore = useCallback(async () => {
    if (!tokenStore.get()) {
      setBooting(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch (err) {
      if (err instanceof Error && (err as { status?: number }).status === 401) {
        clearSession();
      }
    } finally {
      setBooting(false);
    }
  }, [clearSession]);

  useEffect(() => {
    restore();
    const onExpired = () => clearSession();
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [restore, clearSession]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const signup = useCallback(async (email: string, password: string, fullName: string) => {
    const res = await api.register(email, password, fullName);
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(() => clearSession(), [clearSession]);

  const refreshUser = useCallback(async () => {
    const u = await api.me();
    setUser(u);
  }, []);

  const value = useMemo(
    () => ({ user, booting, loggedIn: user !== null, login, signup, logout, refreshUser }),
    [user, booting, login, signup, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}