async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) {
        detail = body.detail.map((item) => item.msg || "Invalid value").join(" ");
      }
    } catch {
      /* keep the status text */
    }
    throw new Error(detail || "Request failed");
  }
  if (response.status === 204) return null;
  return response.json();
}

function queryString(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  health: () => request("/api/health"),
  analytics: () => request("/api/analytics/overview"),
  metrics: () => request("/api/models/metrics"),
  departments: () => request("/api/departments"),
  tickets: (params) => request(`/api/tickets${queryString(params)}`),
  ticket: (id) => request(`/api/tickets/${id}`),
  createTicket: (body) => request("/api/tickets", { method: "POST", body: JSON.stringify(body) }),
  validate: (id, body) => request(`/api/tickets/${id}/validation`, { method: "POST", body: JSON.stringify(body) }),
  suggest: (id) => request(`/api/tickets/${id}/suggestion`, { method: "POST" }),
  reply: (id, body) => request(`/api/tickets/${id}/replies`, { method: "POST", body: JSON.stringify(body) }),
  setStatus: (id, status) => request(`/api/tickets/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  search: (q) => request(`/api/search${queryString({ q, limit: 8 })}`),
};
