"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ToastItem {
  id: string;
  type: "transaction" | "contradiction" | "score" | "info";
  message: string;
  detail?: string;
  link?: string;
  timestamp: number;
}

type AddToastPayload = Omit<ToastItem, "id" | "timestamp">;

interface ToastContextValue {
  addToast: (toast: AddToastPayload) => void;
  removeToast: (id: string) => void;
  toasts: ToastItem[];
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): { addToast: (toast: AddToastPayload) => void; toasts: ToastItem[] } {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a <ToastProvider>");
  }
  return { addToast: ctx.addToast, toasts: ctx.toasts };
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_VISIBLE = 3;
const AUTO_DISMISS_MS = 5000;

let _counter = 0;
function uniqueId(): string {
  _counter += 1;
  return `toast-${Date.now()}-${_counter}`;
}

// ---------------------------------------------------------------------------
// Border color per type
// ---------------------------------------------------------------------------

function borderColor(type: ToastItem["type"]): string {
  switch (type) {
    case "transaction":
      return "border-l-[var(--accent)]";
    case "contradiction":
      return "border-l-[var(--status-error)]";
    case "score":
      return "border-l-[var(--status-success)]";
    case "info":
    default:
      return "border-l-[var(--text-ghost)]";
  }
}

function badgeClass(type: ToastItem["type"]): string {
  switch (type) {
    case "transaction":
      return "text-[var(--accent)] bg-[var(--accent-muted)]";
    case "contradiction":
      return "text-[var(--status-error)] bg-[rgba(248,113,113,0.1)]";
    case "score":
      return "text-[var(--status-success)] bg-[rgba(52,211,153,0.1)]";
    case "info":
    default:
      return "text-[var(--text-tertiary)] bg-[var(--bg-surface-2)]";
  }
}

function formatTime(ts: number): string {
  const now = Date.now();
  const diff = Math.floor((now - ts) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  return `${Math.floor(diff / 60)}m ago`;
}

// ---------------------------------------------------------------------------
// Single Toast
// ---------------------------------------------------------------------------

function ToastCard({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const [phase, setPhase] = useState<"enter" | "visible" | "exit">("enter");
  const [relativeTime, setRelativeTime] = useState(() => formatTime(item.timestamp));
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setPhase("visible"), 20);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    timerRef.current = setTimeout(() => {
      setPhase("exit");
    }, AUTO_DISMISS_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (phase === "exit") {
      const t = setTimeout(() => onDismiss(item.id), 300);
      return () => clearTimeout(t);
    }
  }, [phase, item.id, onDismiss]);

  useEffect(() => {
    const interval = setInterval(() => {
      setRelativeTime(formatTime(item.timestamp));
    }, 10_000);
    return () => clearInterval(interval);
  }, [item.timestamp]);

  const translateX =
    phase === "enter" || phase === "exit" ? "translate-x-full" : "translate-x-0";
  const opacity = phase === "exit" ? "opacity-0" : "opacity-100";

  return (
    <div
      className={[
        "w-80 glass border border-[var(--border-default)] border-l-2 rounded-xl",
        "shadow-lg",
        borderColor(item.type),
        "transition-all duration-300 ease-out",
        translateX,
        opacity,
      ].join(" ")}
      role="status"
      aria-live="polite"
    >
      <div className="px-3.5 py-3 flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span
            className={`text-[11px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-md ${badgeClass(item.type)}`}
          >
            {item.type}
          </span>
          <span className="text-[11px] text-[var(--text-ghost)] font-mono">
            {relativeTime}
          </span>
        </div>

        <p className="text-[13px] text-[var(--text-primary)] leading-relaxed">{item.message}</p>

        {item.detail && (
          <p className="text-[12px] text-[var(--text-tertiary)] leading-snug">{item.detail}</p>
        )}

        {item.link && (
          <Link
            href={item.link}
            className="text-[12px] text-[var(--accent)] hover:text-[var(--accent-hover)] hover:underline self-start mt-0.5"
          >
            View &rarr;
          </Link>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToastContainer
// ---------------------------------------------------------------------------

export function ToastContainer() {
  const ctx = useContext(ToastContext);
  if (!ctx) return null;

  const { toasts, removeToast } = ctx;
  const visible = toasts.slice(-MAX_VISIBLE);

  return (
    <div className="fixed bottom-4 right-4 z-[90] flex flex-col-reverse gap-2">
      {visible.map((item) => (
        <ToastCard key={item.id} item={item} onDismiss={removeToast} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToastProvider
// ---------------------------------------------------------------------------

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((payload: AddToastPayload) => {
    const item: ToastItem = {
      ...payload,
      id: uniqueId(),
      timestamp: Date.now(),
    };
    setToasts((prev) => {
      const next = [...prev, item];
      if (next.length > MAX_VISIBLE * 2) {
        return next.slice(-MAX_VISIBLE * 2);
      }
      return next;
    });
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value: ToastContextValue = { addToast, removeToast, toasts };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  );
}

export default ToastProvider;
