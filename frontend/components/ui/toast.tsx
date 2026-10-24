"use client";
// Toast: a short confirmation that never blocks. Announced politely, dismisses itself after 4 s, one quick fade.
import { Check, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactElement, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ToastOptions {
  title: string;
  description?: string;
  /** "error" is announced assertively and stays until dismissed. */
  tone?: "default" | "error";
  /** One quiet action beside the message, for example Undo. Taking it dismisses the toast. */
  action?: { label: string; onClick: () => void };
}

interface ToastItem extends ToastOptions {
  id: number;
}

type ToastFn = (options: ToastOptions | string) => void;

const ToastContext = createContext<ToastFn>(() => {});

/** Show a toast from anywhere under <ToastProvider>. A no-op outside it. */
export function useToast(): ToastFn {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }): ReactElement {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    setItems((list) => list.filter((t) => t.id !== id));
    const t = timers.current.get(id);
    if (t) clearTimeout(t);
    timers.current.delete(id);
  }, []);

  const toast = useCallback<ToastFn>(
    (options) => {
      const o = typeof options === "string" ? { title: options } : options;
      const id = next.current++;
      setItems((list) => [...list.slice(-2), { ...o, id }]);
      if (o.tone !== "error") timers.current.set(id, setTimeout(() => dismiss(id), 4000));
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((t) => clearTimeout(t));
  }, []);

  const value = useMemo(() => toast, [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-toast flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2" data-print-hide>
        {items.map((t) => (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex animate-rise-in items-start gap-2.5 rounded-lg border bg-cream px-3.5 py-3 text-sm shadow-lg",
              t.tone === "error" ? "border-sindoor/60" : "border-line",
            )}
          >
            {t.tone !== "error" ? <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-neem" /> : null}
            <div className="min-w-0 flex-1">
              <p className={cn("font-medium", t.tone === "error" ? "text-sindoor" : "text-ink")}>{t.title}</p>
              {t.description ? <p className="mt-0.5 text-ink-soft">{t.description}</p> : null}
            </div>
            {t.action ? (
              <button
                type="button"
                onClick={() => {
                  t.action?.onClick();
                  dismiss(t.id);
                }}
                className="shrink-0 rounded-sm px-1 text-sm font-medium text-maroon underline-offset-4 hover:underline"
              >
                {t.action.label}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="grid size-6 shrink-0 place-items-center rounded-sm text-ink-muted hover:bg-ink/[0.06] hover:text-ink"
            >
              <X aria-hidden className="size-3.5" />
              <span className="sr-only">Dismiss</span>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
