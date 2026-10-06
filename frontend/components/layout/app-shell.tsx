"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  ArrowLeftFromLine,
  ArrowRightFromLine,
  Command,
  FilePlus2,
  LayoutDashboard,
  LogOut,
  Menu,
  Shield,
  Workflow,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { CommandPalette } from "@/components/navigation/command-palette";
import { canAccessAdmin, isDemoUser } from "@/lib/auth/access";
import { useToast } from "@/components/ui/toast";
import { explainApiError } from "@/lib/api/errors";
import { safeReturnPath } from "@/lib/auth/return-path";

const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Workflow },
  { href: "/submit", label: "Submit job", icon: FilePlus2 },
  { href: "/activity", label: "Activity", icon: Activity },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useAuth();
  const { show } = useToast();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const title = useMemo(() => {
    if (pathname.startsWith("/jobs/")) return "Job execution";
    if (pathname === "/admin") return "Admin operations";
    return navigation.find((item) => item.href === pathname)?.label ?? "Operations";
  }, [pathname]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const onNavigate = () => setMobileOpen(false);
  const initials = user?.email.slice(0, 1).toUpperCase() ?? "A";
  const demo = isDemoUser(user);
  const links = canAccessAdmin(user)
    ? [...navigation, { href: "/admin", label: "Admin operations", icon: Shield }]
    : navigation.filter((item) => !demo || item.href !== "/submit");
  const accountRole = demo ? "DEMO · READ ONLY" : canAccessAdmin(user) ? "ADMIN" : "USER";

  return (
    <div className="app-frame">
      {mobileOpen && <button className="mobile-backdrop" aria-label="Close navigation" onClick={onNavigate} />}
      <aside id="primary-navigation" className={`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`} aria-label="Main navigation">
        <Link href="/" className="brand" onClick={onNavigate} aria-label="AetherFlow overview">
          <span className="brand-mark"><Activity size={17} strokeWidth={1.8} /></span>
          <span className="brand-copy">
            <span className="brand-word">AETHERFLOW</span>
            <span className="brand-caption" style={{ display: "block", marginTop: 1 }}>JOB ORCHESTRATION</span>
          </span>
        </Link>
        <div className="sidebar-section">Workspace</div>
        <nav className="nav-list">
          {links.map((item) => {
            const Icon = item.icon;
            const active = item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                href={item.href}
                key={item.href}
                className={`nav-link ${active ? "active" : ""} ${item.href === "/admin" ? "nav-admin" : ""}`}
                aria-current={active ? "page" : undefined}
                title={item.label}
                onClick={onNavigate}
              >
                <Icon size={17} strokeWidth={1.7} />
                <span className="nav-label">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <button className="sidebar-collapse" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <ArrowRightFromLine size={16} /> : <ArrowLeftFromLine size={16} />}
            <span>{collapsed ? "Expand sidebar" : "Collapse sidebar"}</span>
          </button>
          <div className="sidebar-account">
            <span className="account-avatar" aria-hidden="true">{initials}</span>
            <span className="brand-copy" style={{ minWidth: 0, flex: 1 }}>
              <span className="account-name" style={{ display: "block", maxWidth: 150 }}>{user?.email}</span>
              <span className="account-role" style={{ display: "block", marginTop: 2 }}>{accountRole}</span>
            </span>
            <button
              className="icon-button"
              aria-label="Sign out"
              title="Sign out"
              onClick={() => void signOut().catch((error: unknown) => show(explainApiError(error), "error")).finally(() => router.replace("/login"))}
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>
      <div className={`main-column ${collapsed ? "sidebar-collapsed" : ""}`}>
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" aria-controls="primary-navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}>
            <Menu size={18} />
          </button>
          <div className="crumb">
            <span>CONTROL PLANE</span><span aria-hidden="true">/</span><span className="crumb-current">{title}</span>
          </div>
          <div className="topbar-actions">
            <button className="command-trigger" onClick={() => setPaletteOpen(true)} aria-label="Open command palette">
              <span className="command-trigger-text"><Command size={13} /><span>Jump to…</span></span>
              <kbd>⌘ K</kbd>
            </button>
            <span className="account-chip">
              <span className="account-avatar" aria-hidden="true">{initials}</span>
              <span>
                <span className="account-name" style={{ display: "block" }}>{user?.email}</span>
                <span className="account-role" style={{ display: "block", textAlign: "right" }}>{accountRole}</span>
              </span>
            </span>
          </div>
        </header>
        {demo && (
          <div className="demo-banner" role="note">
            <strong>DEMO WORKSPACE</strong>
            <span>Read-only seeded examples. Job execution and administrative actions are disabled.</span>
          </div>
        )}
        <main className="content" id="main-content" key={pathname}>
          {children}
        </main>
      </div>
      <CommandPalette key={paletteOpen ? "open" : "closed"} open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}

export function ProtectedLayout({ children }: { children: ReactNode }) {
  const { status, retrySession } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      const destination = `${window.location.pathname}${window.location.search}`;
      const next = safeReturnPath(destination);
      router.replace(next ? `/login?next=${encodeURIComponent(next)}` : "/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return <div className="center-state"><div style={{ display: "grid", justifyItems: "center", gap: 12 }}><span className="screen-spinner" /><span className="muted" style={{ fontSize: 11 }}>Restoring secure session…</span></div></div>;
  }
  if (status === "unavailable") {
    return (
      <div className="center-state">
        <div style={{ width: "min(430px, 100%)" }}>
          <div className="brand" style={{ padding: 0, marginBottom: 28 }}><span className="brand-mark"><Activity size={17} /></span><span className="brand-word">AETHERFLOW</span></div>
          <div className="notice"><X size={16} /><div style={{ flex: 1 }}><strong>API unavailable</strong><div>The console could not restore a session because the API did not respond.</div></div></div>
          <ButtonRetry onRetry={() => void retrySession()} />
          <Link href="/login" className="table-link" style={{ display: "block", marginTop: 16, fontSize: 11 }}>Continue to sign in</Link>
        </div>
      </div>
    );
  }
  if (status === "unauthenticated") return null;
  return <AppShell>{children}</AppShell>;
}

function ButtonRetry({ onRetry }: { onRetry(): void }) {
  return <button className="button" style={{ marginTop: 18 }} onClick={onRetry}>Retry connection</button>;
}
