"use client";

import { useEffect, useRef, type ReactNode, type ButtonHTMLAttributes } from "react";
import {
  Activity,
  Ban,
  Check,
  CircleDashed,
  CircleDot,
  CircleHelp,
  CircleX,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  LoaderCircle,
  RotateCcw,
  X,
} from "lucide-react";
import { formatState } from "@/lib/jobs/state";
import type { JobState } from "@/types/api";
import { useToast } from "@/components/ui/toast";

export function Button({
  variant = "secondary",
  size = "normal",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "normal" | "small";
}) {
  return (
    <button
      {...props}
      className={`button ${variant} ${size === "small" ? "small" : ""} ${className}`.trim()}
    />
  );
}

const statusIcons: Record<JobState, typeof CircleDot> = {
  ACCEPTED: CircleDashed,
  QUEUED: Clock3,
  RUNNING: Activity,
  RETRY_SCHEDULED: RotateCcw,
  DEAD_LETTERED: CircleX,
  CANCEL_REQUESTED: Ban,
  CANCELLED: X,
  SUCCEEDED: Check,
  FAILED: CircleX,
};

export function StatusBadge({ state }: { state: JobState }) {
  const Icon = statusIcons[state] ?? CircleHelp;
  return (
    <span className={`status-badge status-${state.toLowerCase()}`} aria-label={`State: ${formatState(state)}`}>
      <Icon size={12} className={state === "RUNNING" ? "status-pulse" : undefined} aria-hidden="true" />
      {formatState(state)}
    </span>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div>
        <div className="empty-icon">{icon}</div>
        <h3 className="empty-title">{title}</h3>
        <p className="empty-description">{description}</p>
        {action}
      </div>
    </div>
  );
}

export function ErrorNotice({
  title = "This view could not be loaded",
  message,
  requestId,
  onRetry,
}: {
  title?: string;
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="notice" role="alert">
      <CircleX size={16} />
      <div style={{ flex: 1 }}>
        <strong>{title}</strong>
        <div>{message}</div>
        {requestId && <div className="mono muted" style={{ marginTop: 4 }}>Request {requestId}</div>}
      </div>
      {onRetry && <Button size="small" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const { show } = useToast();
  return (
    <button
      className="icon-button"
      aria-label={label}
      title={label}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          show("Copied to clipboard.", "success");
        } catch {
          show("Clipboard access is unavailable in this browser.", "error");
        }
      }}
    >
      <Copy size={14} />
    </button>
  );
}

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = "Confirm",
  busy = false,
  danger = false,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  busy?: boolean;
  danger?: boolean;
  onCancel(): void;
  onConfirm(): void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    ref.current?.querySelector<HTMLElement>("button")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel();
      if (event.key === "Tab" && ref.current) {
        const controls = Array.from(
          ref.current.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled)'),
        );
        if (!controls.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onCancel]);
  if (!open) return null;
  return (
    <div className="dialog-overlay" onMouseDown={(event) => event.target === event.currentTarget && !busy && onCancel()}>
      <div
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        ref={ref}
        tabIndex={-1}
      >
        <h2 className="dialog-title" id="confirm-dialog-title">{title}</h2>
        <div className="dialog-copy">{children}</div>
        <div className="dialog-actions">
          <Button variant="ghost" disabled={busy} onClick={onCancel}>Keep job</Button>
          <Button variant={danger ? "danger" : "primary"} disabled={busy} onClick={onConfirm}>
            {busy && <LoaderCircle size={14} className="status-pulse" />}
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div aria-label="Loading jobs" aria-busy="true">
      {Array.from({ length: count }, (_, index) => <div className="skeleton-row" key={index} />)}
    </div>
  );
}

export function Pagination({
  offset,
  limit,
  count,
  hasNext,
  onChange,
}: {
  offset: number;
  limit: number;
  count: number;
  hasNext: boolean;
  onChange(offset: number): void;
}) {
  const page = Math.floor(offset / limit) + 1;
  return (
    <div className="table-footer">
      <span>{count ? `${count} records in this page` : "No records in this page"}</span>
      <div className="pagination">
        <button className="icon-button" disabled={offset === 0} aria-label="Previous page" onClick={() => onChange(Math.max(0, offset - limit))}>
          <ChevronLeft size={14} />
        </button>
        <span className="page-count">Page {page}</span>
        <button className="icon-button" disabled={!hasNext} aria-label="Next page" onClick={() => onChange(offset + limit)}>
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
