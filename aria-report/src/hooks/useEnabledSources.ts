import { useState } from "react";

const STORAGE_KEY = "aria-enabled-sources";

function getStored(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function useEnabledSources() {
  const [overrides, setOverrides] = useState<Record<string, boolean>>(getStored);

  /** Whether a source is active. Falls back to `defaultVal` if user never touched it. */
  function isEnabled(id: string, defaultVal: boolean): boolean {
    return id in overrides ? overrides[id] : defaultVal;
  }

  /** Flip the toggle for a source. */
  function toggle(id: string, defaultVal: boolean) {
    setOverrides((prev) => {
      const current = id in prev ? prev[id] : defaultVal;
      const next = { ...prev, [id]: !current };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  return { isEnabled, toggle };
}
