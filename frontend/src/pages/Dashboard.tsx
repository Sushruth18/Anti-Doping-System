import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getAthletes } from "../api/client";
import type { AthleteListItem } from "../types/api";
import {
  Search,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Users,
  AlertTriangle,
  TrendingUp,
  Activity,
  X,
  ArrowUpRight,
  ShieldAlert,
  ArrowUpDown,
  Filter,
} from "lucide-react";

/* ── Severity helpers ──────────────────────────────────────── */
function getSeverity(athlete: AthleteListItem): "critical" | "elevated" | "moderate" | "clean" | "unscored" {
  if (!athlete.scored) return "unscored";
  const pct = athlete.priority_score;
  if (pct >= 0.90) return "critical";
  if (pct >= 0.70) return "elevated";
  if (pct >= 0.55) return "moderate";
  return "clean";
}

const SEVERITY_LABELS: Record<string, string> = {
  critical:  "Critical",
  elevated:  "Elevated",
  moderate:  "Moderate",
  clean:     "Clean",
  unscored:  "Unscored",
};

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  elevated: 1,
  moderate: 2,
  clean: 3,
  unscored: 4,
};

/* ── Score bar ─────────────────────────────────────────────── */
function ScoreBar({ value, severity }: { value: number; severity: string }) {
  const colors: Record<string, string> = {
    critical: "#ef4444",
    elevated: "#f97316",
    moderate: "#f59e0b",
    clean: "#10b981",
    unscored: "#64748b",
  };
  const color = colors[severity] ?? "#64748b";
  const pct = Math.round(value * 100);
  return (
    <div className="score-bar-wrap" style={{ minWidth: 110 }}>
      <div className="score-bar-track">
        <div
          className="score-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="score-bar-label" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

/* ── Sort types ────────────────────────────────────────────── */
type SortKey =
  | "id"
  | "name"
  | "sport"
  | "age"
  | "priority_score"
  | "latest_anomaly_score"
  | "last_sample_date"
  | "severity";

type SortDir = "asc" | "desc";

/* ── Sort icon ─────────────────────────────────────────────── */
function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (col !== sortKey) return <ChevronsUpDown size={12} style={{ opacity: 0.35 }} />;
  return sortDir === "asc"
    ? <ChevronUp size={12} style={{ color: "var(--primary)" }} />
    : <ChevronDown size={12} style={{ color: "var(--primary)" }} />;
}

/* ── Main Dashboard Component ──────────────────────────────── */
function Dashboard() {
  const navigate = useNavigate();
  const [athletes, setAthletes] = useState<AthleteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [query, setQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("priority_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  useEffect(() => {
    getAthletes()
      .then(setAthletes)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  /* ── KPIs ──────────────────────────────────────────────── */
  const kpis = useMemo(() => {
    const scored = athletes.filter((a) => a.scored);
    const critical = scored.filter((a) => a.priority_score >= 0.90).length;
    const elevated = scored.filter((a) => a.priority_score >= 0.70 && a.priority_score < 0.90).length;
    const moderate = scored.filter((a) => a.priority_score >= 0.55 && a.priority_score < 0.70).length;
    const clean    = scored.filter((a) => a.priority_score < 0.55).length;
    const unscored = athletes.filter((a) => !a.scored).length;
    return { total: athletes.length, scored: scored.length, critical, elevated, moderate, clean, unscored };
  }, [athletes]);

  /* ── Filtering ─────────────────────────────────────────── */
  const filtered = useMemo(() => {
    let list = athletes;

    // 1. Filter by risk status chip
    if (riskFilter !== "all") {
      list = list.filter((a) => getSeverity(a) === riskFilter);
    }

    // 2. Filter by search query
    const q = query.toLowerCase().trim();
    if (q) {
      list = list.filter((a) =>
        [
          String(a.id),
          `#${String(a.id).padStart(3, "0")}`,
          a.name,
          a.sport,
          getSeverity(a),
          SEVERITY_LABELS[getSeverity(a)],
          a.last_sample_date ?? "",
        ]
          .join(" ")
          .toLowerCase()
          .includes(q)
      );
    }

    return list;
  }, [athletes, query, riskFilter]);

  /* ── Sorting ───────────────────────────────────────────── */
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let av: string | number;
      let bv: string | number;
      switch (sortKey) {
        case "id":                 av = a.id; bv = b.id; break;
        case "name":               av = a.name; bv = b.name; break;
        case "sport":              av = a.sport; bv = b.sport; break;
        case "age":                av = a.age; bv = b.age; break;
        case "priority_score":     av = a.priority_score; bv = b.priority_score; break;
        case "latest_anomaly_score": av = a.latest_anomaly_score ?? -1; bv = b.latest_anomaly_score ?? -1; break;
        case "last_sample_date":   av = a.last_sample_date ?? ""; bv = b.last_sample_date ?? ""; break;
        case "severity":           av = SEVERITY_ORDER[getSeverity(a)]; bv = SEVERITY_ORDER[getSeverity(b)]; break;
        default:                   av = a.priority_score; bv = b.priority_score;
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
  }, [filtered, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  /* Preset dropdown sorting handler */
  const handlePresetSort = (preset: string) => {
    switch (preset) {
      case "priority":
        setSortKey("priority_score");
        setSortDir("desc");
        break;
      case "highest_anomaly":
        setSortKey("latest_anomaly_score");
        setSortDir("desc");
        break;
      case "lowest_anomaly":
        setSortKey("latest_anomaly_score");
        setSortDir("asc");
        break;
      case "highest_risk":
        setSortKey("severity");
        setSortDir("asc");
        break;
      case "lowest_risk":
        setSortKey("severity");
        setSortDir("desc");
        break;
      case "id":
        setSortKey("id");
        setSortDir("asc");
        break;
      case "recent_sample":
        setSortKey("last_sample_date");
        setSortDir("desc");
        break;
    }
  };

  /* ── Loading Skeleton ──────────────────────────────────── */
  if (loading) {
    return (
      <div style={{ padding: "28px 32px", maxWidth: "1440px", margin: "0 auto" }}>
        <div style={{ marginBottom: 24 }}>
          <div className="skeleton" style={{ width: 260, height: 26, marginBottom: 8 }} />
          <div className="skeleton" style={{ width: 380, height: 16 }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 24 }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton" style={{ height: 92, borderRadius: 10 }} />
          ))}
        </div>
        <div className="skeleton" style={{ height: 420, borderRadius: 10 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "28px 32px", maxWidth: "1440px", margin: "0 auto" }}>
        <div
          className="panel"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "80px 20px",
            gap: 12,
          }}
        >
          <AlertTriangle size={36} color="#ef4444" />
          <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: "var(--foreground)", margin: 0 }}>
            Failed to Connect to Intelligence API
          </h2>
          <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", margin: 0 }}>
            Please ensure that the FastAPI backend server is running.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "26px 32px 60px", maxWidth: "1440px", margin: "0 auto" }}>
      {/* ── Page Header (NO PRINT BUTTON HERE) ────────────────── */}
      <div
        className="animate-fade-in"
        style={{
          marginBottom: 24,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h1
              style={{
                fontSize: "1.375rem",
                fontWeight: 800,
                color: "var(--foreground)",
                letterSpacing: "-0.02em",
                margin: 0,
              }}
            >
              Anti-Doping Intelligence Command Center
            </h1>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 600,
                color: "#38bdf8",
                background: "rgba(56, 189, 248, 0.12)",
                padding: "2px 8px",
                borderRadius: 4,
                border: "1px solid rgba(56, 189, 248, 0.25)",
              }}
            >
              LIVE COHORT
            </span>
          </div>
          <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", margin: "4px 0 0" }}>
            Priority-ranked biological passport monitoring · {athletes.length} total athletes · {kpis.scored} evaluated
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--muted-foreground)",
              fontFamily: "var(--font-mono)",
              background: "var(--muted)",
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid var(--border)",
            }}
          >
            {kpis.critical > 0 ? (
              <span style={{ color: "#ef4444", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <ShieldAlert size={13} /> {kpis.critical} HIGH PRIORITY TARGET{kpis.critical !== 1 ? "S" : ""}
              </span>
            ) : (
              <span style={{ color: "#10b981" }}>● All Profiles Stable</span>
            )}
          </div>
        </div>
      </div>

      {/* ── KPI Summary Cards ─────────────────────────────────── */}
      <div
        className="animate-fade-in"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
          gap: "14px",
          marginBottom: "24px",
        }}
      >
        {/* Total Athletes */}
        <div className="stat-card" onClick={() => setRiskFilter("all")} style={{ cursor: "pointer" }}>
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <Users size={12} color="var(--muted-foreground)" /> Total Athletes
          </div>
          <div className="stat-card-value">{kpis.total}</div>
          <div className="stat-card-sub">{kpis.scored} scored · {kpis.unscored} unscored</div>
        </div>

        {/* Critical */}
        <div
          className="stat-card"
          onClick={() => setRiskFilter("critical")}
          style={{
            cursor: "pointer",
            border: riskFilter === "critical" ? "1px solid #ef4444" : "1px solid var(--border)",
            background: riskFilter === "critical" ? "rgba(239, 68, 68, 0.08)" : "var(--card)",
          }}
        >
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5, color: "#ef4444" }}>
            <AlertTriangle size={12} /> Critical Risk
          </div>
          <div className="stat-card-value" style={{ color: "#ef4444" }}>{kpis.critical}</div>
          <div className="stat-card-sub">≥ 90% priority score</div>
        </div>

        {/* Elevated */}
        <div
          className="stat-card"
          onClick={() => setRiskFilter("elevated")}
          style={{
            cursor: "pointer",
            border: riskFilter === "elevated" ? "1px solid #f97316" : "1px solid var(--border)",
            background: riskFilter === "elevated" ? "rgba(249, 115, 22, 0.08)" : "var(--card)",
          }}
        >
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5, color: "#f97316" }}>
            <TrendingUp size={12} /> Elevated Risk
          </div>
          <div className="stat-card-value" style={{ color: "#f97316" }}>{kpis.elevated}</div>
          <div className="stat-card-sub">70 – 89% priority</div>
        </div>

        {/* Moderate */}
        <div
          className="stat-card"
          onClick={() => setRiskFilter("moderate")}
          style={{
            cursor: "pointer",
            border: riskFilter === "moderate" ? "1px solid #f59e0b" : "1px solid var(--border)",
            background: riskFilter === "moderate" ? "rgba(245, 158, 11, 0.08)" : "var(--card)",
          }}
        >
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5, color: "#f59e0b" }}>
            <Activity size={12} /> Moderate Risk
          </div>
          <div className="stat-card-value" style={{ color: "#f59e0b" }}>{kpis.moderate}</div>
          <div className="stat-card-sub">55 – 69% priority</div>
        </div>

        {/* Clean */}
        <div
          className="stat-card"
          onClick={() => setRiskFilter("clean")}
          style={{
            cursor: "pointer",
            border: riskFilter === "clean" ? "1px solid #10b981" : "1px solid var(--border)",
            background: riskFilter === "clean" ? "rgba(16, 185, 129, 0.08)" : "var(--card)",
          }}
        >
          <div className="stat-card-label" style={{ display: "flex", alignItems: "center", gap: 5, color: "#10b981" }}>
            <Activity size={12} /> Normal / Clean
          </div>
          <div className="stat-card-value" style={{ color: "#10b981" }}>{kpis.clean}</div>
          <div className="stat-card-sub">&lt; 55% priority score</div>
        </div>
      </div>

      {/* ── Filter / Search / Sort Controls Bar ───────────────── */}
      <div
        className="panel animate-fade-in"
        style={{ marginBottom: 16, padding: "14px 20px", background: "var(--card)" }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 14,
          }}
        >
          {/* Search Input */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 260, maxWidth: 440 }}>
            <div className="search-input-wrap" style={{ flex: 1 }}>
              <Search className="search-input-icon" />
              <input
                id="athlete-search"
                className="search-input"
                type="text"
                placeholder="Search by ID (#001), athlete name, sport..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search athletes"
              />
            </div>
            {query && (
              <button
                className="btn btn-ghost"
                style={{ padding: "6px 8px" }}
                onClick={() => setQuery("")}
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Quick Risk Filter Chips */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted-foreground)", textTransform: "uppercase", marginRight: 2, display: "flex", alignItems: "center", gap: 4 }}>
              <Filter size={11} /> Filter:
            </span>
            {[
              { key: "all", label: `All (${athletes.length})` },
              { key: "critical", label: `Critical (${kpis.critical})` },
              { key: "elevated", label: `Elevated (${kpis.elevated})` },
              { key: "moderate", label: `Moderate (${kpis.moderate})` },
              { key: "clean", label: `Clean (${kpis.clean})` },
            ].map((chip) => (
              <button
                key={chip.key}
                onClick={() => setRiskFilter(chip.key)}
                className={`filter-chip ${riskFilter === chip.key ? "active" : ""}`}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Sort Dropdown */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "0.6875rem", fontWeight: 600, color: "var(--muted-foreground)", textTransform: "uppercase", display: "flex", alignItems: "center", gap: 4 }}>
              <ArrowUpDown size={11} /> Sort by:
            </span>
            <select
              className="form-select"
              style={{ width: "auto", minWidth: 170, padding: "5px 10px", fontSize: "0.75rem", height: 32 }}
              onChange={(e) => handlePresetSort(e.target.value)}
              defaultValue="priority"
            >
              <option value="priority">Priority Rank (Default)</option>
              <option value="highest_anomaly">Highest Anomaly Score</option>
              <option value="lowest_anomaly">Lowest Anomaly Score</option>
              <option value="highest_risk">Highest Risk Level</option>
              <option value="lowest_risk">Lowest Risk Level</option>
              <option value="id">Athlete ID</option>
              <option value="recent_sample">Most Recent Sample</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── Athlete Table Panel ───────────────────────────────── */}
      <div className="panel animate-fade-in">
        {/* Table Header Info */}
        <div className="panel-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="panel-title">Monitored Athlete Roster</span>
            <span
              style={{
                fontSize: "0.6875rem",
                fontWeight: 600,
                color: "var(--muted-foreground)",
                padding: "2px 8px",
                background: "var(--muted)",
                borderRadius: 4,
                border: "1px solid var(--border)",
              }}
            >
              {sorted.length} of {athletes.length} displayed
            </span>
          </div>

          {(query || riskFilter !== "all") && (
            <button
              onClick={() => {
                setQuery("");
                setRiskFilter("all");
              }}
              className="btn btn-ghost"
              style={{ fontSize: "0.6875rem", padding: "4px 8px", color: "var(--primary)" }}
            >
              Reset Filters
            </button>
          )}
        </div>

        {/* Table */}
        <div style={{ overflowX: "auto" }}>
          <table className="nada-table">
            <thead>
              <tr>
                {(
                  [
                    { key: "id",                   label: "Athlete ID" },
                    { key: "name",                 label: "Athlete Name" },
                    { key: "sport",                label: "Sport" },
                    { key: "age",                  label: "Age" },
                    { key: "severity",             label: "Risk Assessment" },
                    { key: "priority_score",       label: "Investigation Priority" },
                    { key: "latest_anomaly_score", label: "Anomaly Score" },
                    { key: "last_sample_date",     label: "Latest Sample" },
                  ] as { key: SortKey; label: string }[]
                ).map(({ key, label }) => (
                  <th
                    key={key}
                    className="sortable"
                    onClick={() => toggleSort(key)}
                    aria-sort={sortKey === key ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
                    style={{
                      color: sortKey === key ? "var(--foreground)" : undefined,
                    }}
                  >
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                      {label}
                      <SortIcon col={key} sortKey={sortKey} sortDir={sortDir} />
                    </span>
                  </th>
                ))}
                <th style={{ width: 40 }} />
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr style={{ cursor: "default" }}>
                  <td
                    colSpan={9}
                    style={{
                      padding: "54px 20px",
                      textAlign: "center",
                      color: "var(--muted-foreground)",
                      fontSize: "0.8125rem",
                    }}
                  >
                    No athletes match the current search query or filter criteria.
                  </td>
                </tr>
              ) : (
                sorted.map((athlete) => {
                  const sev = getSeverity(athlete);
                  return (
                    <tr
                      key={athlete.id}
                      onClick={() => navigate(`/athlete/${athlete.id}`)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") navigate(`/athlete/${athlete.id}`);
                      }}
                    >
                      {/* ID */}
                      <td>
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "0.75rem",
                            color: "var(--muted-foreground)",
                            background: "rgba(255,255,255,0.03)",
                            padding: "2px 6px",
                            borderRadius: 4,
                            border: "1px solid var(--border)",
                          }}
                        >
                          #{String(athlete.id).padStart(3, "0")}
                        </span>
                      </td>

                      {/* Name */}
                      <td>
                        <span
                          style={{
                            fontWeight: 600,
                            fontSize: "0.8125rem",
                            color: "var(--foreground)",
                          }}
                        >
                          {athlete.name}
                        </span>
                      </td>

                      {/* Sport */}
                      <td>
                        <span
                          style={{
                            fontSize: "0.8125rem",
                            color: "var(--muted-foreground)",
                          }}
                        >
                          {athlete.sport}
                        </span>
                      </td>

                      {/* Age */}
                      <td>
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "0.8125rem",
                            color: "var(--muted-foreground)",
                          }}
                        >
                          {athlete.age}
                        </span>
                      </td>

                      {/* Risk Assessment Badge */}
                      <td>
                        <span className={`badge badge-${sev === "unscored" ? "neutral" : sev}`}>
                          {SEVERITY_LABELS[sev]}
                        </span>
                      </td>

                      {/* Investigation Priority Meter */}
                      <td style={{ minWidth: 140 }}>
                        {athlete.scored ? (
                          <ScoreBar value={athlete.priority_score} severity={sev} />
                        ) : (
                          <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>—</span>
                        )}
                      </td>

                      {/* Anomaly score */}
                      <td>
                        {athlete.latest_anomaly_score != null ? (
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: "0.8125rem",
                              color: sev === "critical" ? "#ef4444" : sev === "elevated" ? "#f97316" : sev === "moderate" ? "#f59e0b" : "#10b981",
                              fontWeight: 600,
                            }}
                          >
                            {athlete.latest_anomaly_score.toFixed(2)}
                          </span>
                        ) : (
                          <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>—</span>
                        )}
                      </td>

                      {/* Last Sample Date */}
                      <td>
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "0.75rem",
                            color: "var(--muted-foreground)",
                          }}
                        >
                          {athlete.last_sample_date ?? "—"}
                        </span>
                      </td>

                      {/* Chevron Action */}
                      <td style={{ textAlign: "right" }}>
                        <ArrowUpRight
                          size={15}
                          style={{ color: "var(--muted-foreground)", opacity: 0.5 }}
                        />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Footer */}
        <div
          style={{
            padding: "12px 18px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.6875rem",
            color: "var(--muted-foreground)",
            background: "var(--header-bg)",
          }}
        >
          <span>
            Displaying {sorted.length} athlete dossier{sorted.length !== 1 ? "s" : ""} · Click any row to view full biological report
          </span>
          <span style={{ fontFamily: "var(--font-mono)" }}>
            NADA Investigation Platform · Confidential
          </span>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
