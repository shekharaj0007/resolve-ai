export const AGENTS = ["Alex Rivera", "Priya Shah", "Jordan Lee", "Sam Okonkwo"];

export const LABELS = {
  billing: "Billing",
  technical: "Technical Support",
  account: "Account Access",
  shipping: "Orders & Shipping",
  returns: "Returns & Refunds",
  product: "Product Inquiry",
  trust: "Trust & Safety",
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
  negative: "Negative",
  neutral: "Neutral",
  positive: "Positive",
  open: "Open",
  triaged: "Triaged",
  in_progress: "In progress",
  pending_customer: "Pending customer",
  resolved: "Resolved",
};

export const DEPT_COLORS = {
  billing: "#e25b2a",
  technical: "#234e68",
  account: "#6b4c9a",
  shipping: "#1e6b45",
  returns: "#8d5a09",
  product: "#3d6b62",
  trust: "#9d342c",
};

export function labelFor(value) {
  if (!value) return "—";
  return LABELS[value] || value;
}

export function percent(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function minutes(seconds) {
  if (seconds == null) return "—";
  return `${(seconds / 60).toFixed(1)} min`;
}

export function formatAgo(iso) {
  if (!iso) return "";
  const delta = Date.now() - new Date(iso).getTime();
  const mins = Math.round(delta / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 36) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function initials(name) {
  return (name || "?")
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
