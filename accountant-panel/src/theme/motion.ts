import { useEffect, useState } from "react";

export const feedbackDurationSeconds = 4;

export const motion = {
  micro: "var(--motion-micro)",
  standard: "var(--motion-standard)",
  large: "var(--motion-large)",
  enter: "var(--ease-enter)",
  exit: "var(--ease-exit)",
  easing: "var(--ease-standard)",
} as const;

export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(
    () => window.matchMedia(query).matches,
  );
  useEffect(() => {
    const media = window.matchMedia(query);
    const change = () => setMatches(media.matches);
    change();
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, [query]);
  return matches;
}

export const useReducedMotion = () =>
  useMediaQuery("(prefers-reduced-motion: reduce)");

/** Count once per mount. Later refetches update the value without replaying. */
export function CountUp({ value }: { value: number }) {
  const reduced = useReducedMotion();
  const [initial] = useState(value);
  const [display, setDisplay] = useState(initial);
  useEffect(() => {
    if (reduced) return;
    const duration = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        "--motion-count",
      ),
    );
    const started = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const progress = Math.min((now - started) / duration, 1);
      setDisplay(Math.round(initial * (1 - (1 - progress) ** 3)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [initial, reduced]);
  return (reduced || value !== initial ? value : display).toLocaleString(
    "en-GB",
  );
}
