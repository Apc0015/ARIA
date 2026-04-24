import { useEffect, useRef } from "react";
import { animate } from "framer-motion";

interface NumberTickerProps {
  value: number;
  className?: string;
  suffix?: string;
}

export function NumberTicker({ value, className, suffix = "" }: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const prevRef = useRef(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const from = prevRef.current;
    prevRef.current = value;
    const ctrl = animate(from, value, {
      duration: 0.6,
      ease: "easeOut",
      onUpdate(v) {
        node.textContent = Math.round(v).toLocaleString() + suffix;
      },
    });
    return () => ctrl.stop();
  }, [value, suffix]);

  return (
    <span ref={ref} className={className}>
      {value.toLocaleString()}{suffix}
    </span>
  );
}
