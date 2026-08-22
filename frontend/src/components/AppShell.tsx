import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  ShieldCheck,
  Activity,
  AlertTriangle,
} from "lucide-react";
import ThemeToggle from "./ThemeToggle";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const location = useLocation();

  return (
    <div
      style={{
        display: "flex",
        height: "100%",
        minHeight: "100vh",
        background: "var(--background)",
      }}
    >
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside
        className="app-sidebar print-hide"
        style={{
          width: "220px",
          flexShrink: 0,
          background: "var(--sidebar)",
          borderRight: "1px solid var(--sidebar-border)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Logo */}
        <div
          style={{
            padding: "20px 16px 16px",
            borderBottom: "1px solid var(--sidebar-border)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "28px",
                height: "28px",
                background: "var(--primary)",
                borderRadius: "6px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <ShieldCheck size={16} color="#fff" />
            </div>
            <div>
              <div
                style={{
                  fontSize: "0.8125rem",
                  fontWeight: 700,
                  color: "var(--foreground)",
                  letterSpacing: "-0.01em",
                  lineHeight: 1.2,
                }}
              >
                NADA Intel
              </div>
              <div
                style={{
                  fontSize: "0.625rem",
                  fontWeight: 500,
                  color: "var(--muted-foreground)",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                Investigation Platform
              </div>
            </div>
          </div>
        </div>

        {/* Status indicator */}
        <div
          style={{
            padding: "8px 16px",
            borderBottom: "1px solid var(--sidebar-border)",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <div
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: "var(--success)",
              boxShadow: "0 0 6px rgba(34,197,94,0.6)",
            }}
          />
          <span
            style={{
              fontSize: "0.6875rem",
              color: "var(--muted-foreground)",
              fontWeight: 500,
            }}
          >
            System Operational
          </span>
        </div>

        {/* Nav section */}
        <div style={{ padding: "12px 8px", flex: 1 }}>
          <div
            style={{
              fontSize: "0.625rem",
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--muted-foreground)",
              padding: "0 8px",
              marginBottom: "4px",
            }}
          >
            Navigation
          </div>
          <nav style={{ display: "flex", flexDirection: "column", gap: "1px" }}>
            <Link
              to="/"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "9px",
                padding: "7px 8px",
                borderRadius: "6px",
                fontSize: "0.8125rem",
                fontWeight: location.pathname === "/" ? 600 : 400,
                color:
                  location.pathname === "/"
                    ? "var(--foreground)"
                    : "var(--sidebar-foreground)",
                background:
                  location.pathname === "/"
                    ? "var(--sidebar-accent)"
                    : "transparent",
                textDecoration: "none",
                transition: "all 0.12s",
              }}
              onMouseEnter={(e) => {
                if (location.pathname !== "/") {
                  (e.currentTarget as HTMLAnchorElement).style.background =
                    "var(--sidebar-accent)";
                  (e.currentTarget as HTMLAnchorElement).style.color =
                    "var(--foreground)";
                }
              }}
              onMouseLeave={(e) => {
                if (location.pathname !== "/") {
                  (e.currentTarget as HTMLAnchorElement).style.background =
                    "transparent";
                  (e.currentTarget as HTMLAnchorElement).style.color =
                    "var(--sidebar-foreground)";
                }
              }}
            >
              {location.pathname === "/" ? (
                <div
                  style={{
                    width: "3px",
                    height: "14px",
                    background: "var(--primary)",
                    borderRadius: "2px",
                    marginLeft: "-2px",
                  }}
                />
              ) : (
                <div style={{ width: "1px", height: "14px", marginLeft: "-2px" }} />
              )}
              <LayoutDashboard size={15} />
              <span>Dashboard</span>
            </Link>
          </nav>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 16px",
            borderTop: "1px solid var(--sidebar-border)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 8px",
              borderRadius: "6px",
              background: "var(--severity-critical-bg)",
              border: "1px solid var(--severity-critical-border)",
            }}
          >
            <AlertTriangle size={13} color="var(--destructive)" />
            <span
              style={{
                fontSize: "0.6875rem",
                color: "var(--destructive)",
                fontWeight: 600,
                lineHeight: 1.3,
              }}
            >
              Confidential — NADA
            </span>
          </div>
          <div
            style={{
              marginTop: "8px",
              fontSize: "0.625rem",
              color: "var(--muted-foreground)",
              textAlign: "center",
            }}
          >
            NADA Intel v2.0 · SIH 2026
          </div>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────── */}
      <main
        style={{
          flex: 1,
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Top bar */}
        <div
          className="print-hide"
          style={{
            height: "48px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            padding: "0 24px",
            gap: "14px",
            flexShrink: 0,
            background: "var(--card)",
          }}
        >
          <Activity size={14} color="var(--muted-foreground)" />
          <span
            style={{
              fontSize: "0.75rem",
              color: "var(--muted-foreground)",
              fontWeight: 500,
            }}
          >
            Anti-Doping Intelligence & Investigation Platform
          </span>
          <div style={{ flex: 1 }} />
          {/* Theme Toggle */}
          <ThemeToggle />
          <div
            style={{
              fontSize: "0.6875rem",
              color: "var(--muted-foreground)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {new Date().toLocaleDateString("en-IN", {
              day: "2-digit",
              month: "short",
              year: "numeric",
            })}
          </div>
        </div>
        {/* Page content */}
        <div style={{ flex: 1, overflow: "auto" }}>{children}</div>
      </main>
    </div>
  );
}
