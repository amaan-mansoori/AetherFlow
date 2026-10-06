"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Check, CircleAlert, X } from "lucide-react";

type ToastKind = "success" | "error" | "info";
interface ToastMessage { id: number; kind: ToastKind; message: string }
interface ToastValue { show(message: string, kind?: ToastKind): void }

const ToastContext = createContext<ToastValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastMessage[]>([]);
  const show = useCallback((message: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setItems((current) => [...current.slice(-2), { id, kind, message }]);
  }, []);

  useEffect(() => {
    if (!items.length) return;
    const timers = items.map((item) =>
      window.setTimeout(
        () => setItems((current) => current.filter((candidate) => candidate.id !== item.id)),
        4500,
      ),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [items]);

  const value = useMemo(() => ({ show }), [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" aria-live="polite" aria-relevant="additions">
        {items.map((item) => (
          <div className={`toast ${item.kind}`} key={item.id} role="status">
            {item.kind === "success" ? <Check size={15} /> : item.kind === "error" ? <CircleAlert size={15} /> : null}
            <span>{item.message}</span>
            <button
              className="icon-button"
              aria-label="Dismiss notification"
              onClick={() => setItems((current) => current.filter((candidate) => candidate.id !== item.id))}
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastValue {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}
