"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Command, FilePlus2, LayoutDashboard, LogOut, Search, Shield, Workflow } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { canAccessAdmin, isDemoUser } from "@/lib/auth/access";
import { setPendingJobSearch } from "@/lib/navigation/pending-search";
import { useToast } from "@/components/ui/toast";
import { explainApiError } from "@/lib/api/errors";

interface CommandItem {
  label: string;
  description: string;
  href?: string;
  icon: typeof Command;
  action?: () => void;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose(): void }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { user, signOut } = useAuth();
  const demo = isDemoUser(user);
  const { show } = useToast();

  const items = useMemo<CommandItem[]>(() => {
    const routes: CommandItem[] = [
      { label: "Overview", description: "Your current workload snapshot", href: "/", icon: LayoutDashboard },
      { label: "Jobs", description: "Browse and filter submitted jobs", href: "/jobs", icon: Workflow },
      { label: "Activity", description: "Review recent job state updates", href: "/activity", icon: Activity },
    ];
    if (!demo) {
      routes.splice(2, 0, { label: "Submit job", description: "Create an asynchronous inference job", href: "/submit", icon: FilePlus2 });
    }
    if (canAccessAdmin(user)) {
      routes.push({ label: "Admin operations", description: "System-wide job inspection", href: "/admin", icon: Shield });
    }
    routes.push({
      label: "Sign out",
      description: "End this browser session",
      icon: LogOut,
      action: () => {
        void signOut()
          .catch((error: unknown) => show(explainApiError(error), "error"))
          .finally(() => router.replace("/login"));
      },
    });
    return routes;
  }, [user, demo, signOut, router, show]);

  const filtered = useMemo(() => {
    const matching = items.filter((item) =>
      `${item.label} ${item.description}`.toLowerCase().includes(query.toLowerCase()),
    );
    if (query.trim()) {
      matching.unshift({
        label: "Search jobs",
        description: `Filter the visible page for “${query.trim()}”`,
        href: "/jobs",
        icon: Search,
      });
    }
    return matching;
  }, [items, query]);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  if (!open) return null;

  const runItem = (item: CommandItem) => {
    if (query.trim().length > 0 && item.label === "Search jobs") {
      setPendingJobSearch(query.trim());
      window.dispatchEvent(new CustomEvent("aetherflow:job-search"));
    }
    if (item.href) router.push(item.href);
    item.action?.();
    onClose();
  };

  return (
    <div className="command-overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="command-dialog" role="dialog" aria-modal="true" aria-label="Command palette">
        <div className="command-search-row">
          <Search size={17} aria-hidden="true" />
          <input
            ref={input}
            className="command-input"
            aria-label="Search commands"
            placeholder="Navigate or search jobs…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") onClose();
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActive((current) => Math.min(current + 1, filtered.length - 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive((current) => Math.max(0, current - 1));
              }
              if (event.key === "Enter" && filtered[active]) runItem(filtered[active]);
            }}
          />
          <kbd>ESC</kbd>
        </div>
        <div className="command-section-label">{query ? "Matches" : "Navigate"}</div>
        <div className="command-list" role="listbox" aria-label="Commands">
          {filtered.map((item, index) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                role="option"
                aria-selected={active === index}
                className={`command-item ${active === index ? "selected" : ""}`}
                onMouseEnter={() => setActive(index)}
                onClick={() => runItem(item)}
              >
                <Icon size={16} />
                <span style={{ flex: 1 }}>
                  <strong style={{ display: "block", fontSize: 11, fontWeight: 600 }}>{item.label}</strong>
                  <span className="muted" style={{ display: "block", fontSize: 9 }}>{item.description}</span>
                </span>
                {index === active && <kbd>↵</kbd>}
              </button>
            );
          })}
          {!filtered.length && (
            <div className="empty-state" style={{ minHeight: 110 }}>
              <div className="muted" style={{ fontSize: 11 }}>No commands match. Try a page name.</div>
            </div>
          )}
        </div>
        <div className="command-footer">
          <span><kbd>↑</kbd> <kbd>↓</kbd> Navigate</span>
          <span><kbd>↵</kbd> Open</span>
          <span><kbd>esc</kbd> Close</span>
        </div>
      </div>
    </div>
  );
}
