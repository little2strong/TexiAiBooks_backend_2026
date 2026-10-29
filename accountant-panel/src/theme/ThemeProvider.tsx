import {
  createContext,
  useContext,
  useLayoutEffect,
  useState,
  type ReactNode,
} from "react";
import { ConfigProvider } from "antd";
import enGB from "antd/locale/en_GB";
import { useSession } from "../auth/context";
import { getAntdTheme } from "./antd-theme";
import { useMediaQuery, useReducedMotion } from "./motion";

export type ThemeMode = "light" | "dark" | "system";
const ThemeContext = createContext<{
  mode: ThemeMode;
  dark: boolean;
  setMode: (mode: ThemeMode) => void;
} | null>(null);
const keyFor = (id?: string) => `taxiaibooks:appearance:${id || "guest"}`;
function readMode(key: string): ThemeMode {
  try {
    const saved = localStorage.getItem(key);
    if (saved === "light" || saved === "dark" || saved === "system")
      return saved;
  } catch {
    /* Storage may be disabled. */
  }
  return "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const active = useSession();
  const key = keyFor(active?.staff.id);
  const [preference, setPreference] = useState(() => ({
    key,
    mode: readMode(key),
  }));
  const mode = preference.key === key ? preference.mode : readMode(key);
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const reducedMotion = useReducedMotion();
  const dark = mode === "dark" || (mode === "system" && systemDark);
  const [config, setConfig] = useState(() => getAntdTheme(false));
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    setConfig(getAntdTheme(dark, reducedMotion));
  }, [dark, reducedMotion]);
  const setMode = (next: ThemeMode) => {
    setPreference({ key, mode: next });
    try {
      localStorage.setItem(key, next);
    } catch {
      /* The in-memory choice still works. */
    }
  };
  return (
    <ThemeContext.Provider value={{ mode, dark, setMode }}>
      <ConfigProvider locale={enGB} theme={config}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("ThemeProvider is required");
  return context;
}
