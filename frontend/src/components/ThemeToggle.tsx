import { Moon, Sun } from "lucide-react";
import { useTheme } from "../lib/theme";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={!isDark}
      aria-label={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
      title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
      onClick={toggleTheme}
      className="theme-toggle-btn"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "4px 8px 4px 6px",
        borderRadius: "20px",
        border: "1px solid var(--border)",
        background: "var(--muted)",
        color: "var(--foreground)",
        cursor: "pointer",
        fontSize: "0.6875rem",
        fontWeight: 600,
        letterSpacing: "0.02em",
        outline: "none",
        userSelect: "none",
        transition: "all 0.22s ease",
      }}
    >
      {/* Switch pill track */}
      <div
        style={{
          width: "28px",
          height: "16px",
          borderRadius: "10px",
          background: isDark ? "rgba(59, 130, 246, 0.25)" : "rgba(245, 158, 11, 0.3)",
          border: isDark ? "1px solid rgba(59, 130, 246, 0.5)" : "1px solid rgba(245, 158, 11, 0.6)",
          position: "relative",
          display: "flex",
          alignItems: "center",
          padding: "1px",
          transition: "background 0.22s ease, border-color 0.22s ease",
        }}
      >
        <div
          style={{
            width: "12px",
            height: "12px",
            borderRadius: "50%",
            background: isDark ? "#3b82f6" : "#f59e0b",
            boxShadow: isDark
              ? "0 0 6px rgba(59, 130, 246, 0.8)"
              : "0 0 6px rgba(245, 158, 11, 0.8)",
            transform: isDark ? "translateX(0px)" : "translateX(12px)",
            transition: "transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), background 0.22s ease",
          }}
        />
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          minWidth: "48px",
        }}
      >
        {isDark ? (
          <>
            <Moon size={11} color="#94a3b8" />
            <span style={{ color: "var(--muted-foreground)" }}>Dark</span>
          </>
        ) : (
          <>
            <Sun size={11} color="#d97706" />
            <span style={{ color: "#d97706" }}>Light</span>
          </>
        )}
      </div>
    </button>
  );
}

export default ThemeToggle;
