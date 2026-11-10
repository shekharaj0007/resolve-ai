import { DEPT_COLORS, labelFor } from "../format";

export function PageHeader({ kicker, title, lede, children }) {
  return (
    <header className="page-header">
      <div>
        <p className="kicker">{kicker}</p>
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {children && <div className="page-header-actions">{children}</div>}
    </header>
  );
}

export function Badge({ kind, children }) {
  return <span className={`badge ${kind || ""}`}>{children}</span>;
}

export function DepartmentBadge({ department }) {
  if (!department) return null;
  return (
    <span className="badge">
      <i className="dot" style={{ background: DEPT_COLORS[department.slug] || "#6f675d" }} />
      {department.name}
    </span>
  );
}

export function PriorityBadge({ value }) {
  if (!value) return null;
  return <Badge kind={value}>{labelFor(value)}</Badge>;
}

export function SentimentBadge({ value }) {
  if (!value) return null;
  return <Badge kind={value}>{labelFor(value)}</Badge>;
}

export function StatusBadge({ value }) {
  if (!value) return null;
  return <Badge kind={value}>{labelFor(value)}</Badge>;
}

export function Meter({ value }) {
  const width = `${Math.max(0, Math.min(100, Math.round((value || 0) * 100)))}%`;
  return (
    <span className="meter" aria-hidden="true">
      <span style={{ width }} />
    </span>
  );
}
