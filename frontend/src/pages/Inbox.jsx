import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { DepartmentBadge, PageHeader, PriorityBadge, SentimentBadge, StatusBadge } from "../components/ui";
import { formatAgo, labelFor, percent } from "../format";

const EMPTY_FORM = {
  customer_name: "",
  customer_email: "",
  subject: "",
  body: "",
};

const EXAMPLE = {
  customer_name: "Maya Chen",
  customer_email: "maya.chen@fieldnote.example",
  subject: "Charged twice for the Studio plan",
  body: "I'm frustrated that this is still happening. I was charged $49.00 twice for Fieldnote App on order FN-18422. The card ending 4242 shows two captures this morning. This is blocking my work and I need it handled today.",
};

export default function Inbox() {
  const [params, setParams] = useSearchParams();
  const [departments, setDepartments] = useState([]);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [composer, setComposer] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [keyword, setKeyword] = useState(params.get("q") || "");

  const review = params.get("review") || "needs";
  const page = Number(params.get("page") || 1);

  function update(next) {
    const merged = new URLSearchParams(params);
    Object.entries(next).forEach(([key, value]) => {
      if (value) merged.set(key, value);
      else merged.delete(key);
    });
    setParams(merged);
  }

  useEffect(() => {
    api.departments().then(setDepartments).catch(() => setDepartments([]));
  }, []);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    api.tickets({
      q: params.get("q") || "",
      status: params.get("status") || "",
      department: params.get("department") || "",
      priority: params.get("priority") || "",
      review,
      page,
      page_size: 20,
    }).then((next) => {
      if (!ignore) {
        setData(next);
        setError("");
      }
    }).catch((err) => {
      if (!ignore) setError(err.message);
    }).finally(() => {
      if (!ignore) setLoading(false);
    });
    return () => {
      ignore = true;
    };
  }, [params, review, page]);

  async function submitTicket(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const created = await api.createTicket(form);
      window.location.assign(`/tickets/${created.ticket.id}`);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <PageHeader
        kicker="Inbox"
        title="Triage stays with the agent."
        lede="AI labels are a suggestion until someone accepts or corrects them. Nothing in the draft is sent on its own."
      >
        <button className="button" type="button" onClick={() => setComposer(true)}>New ticket</button>
      </PageHeader>

      <form
        className="filters"
        onSubmit={(event) => {
          event.preventDefault();
          update({ q: keyword.trim(), page: "1" });
        }}
      >
        <label className="field">
          Keyword
          <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Invoice, pen, refund..." />
        </label>
        <label className="field">
          Status
          <select value={params.get("status") || ""} onChange={(event) => update({ status: event.target.value, page: "1" })}>
            <option value="">Any status</option>
            {["open", "triaged", "in_progress", "pending_customer", "resolved"].map((status) => (
              <option key={status} value={status}>{labelFor(status)}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Queue
          <select value={params.get("department") || ""} onChange={(event) => update({ department: event.target.value, page: "1" })}>
            <option value="">Any queue</option>
            {departments.map((department) => (
              <option key={department.slug} value={department.slug}>{department.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Priority
          <select value={params.get("priority") || ""} onChange={(event) => update({ priority: event.target.value, page: "1" })}>
            <option value="">Any priority</option>
            {["urgent", "high", "medium", "low"].map((priority) => (
              <option key={priority} value={priority}>{labelFor(priority)}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Review
          <select value={review} onChange={(event) => update({ review: event.target.value, page: "1" })}>
            <option value="needs">Needs review</option>
            <option value="corrected">Corrected</option>
            <option value="accepted">Accepted</option>
            <option value="all">All tickets</option>
          </select>
        </label>
      </form>

      {error && <p className="error-text">{error}</p>}
      <section className="card list-card">
        {loading && <p className="empty">Loading tickets…</p>}
        {!loading && data && data.items.length === 0 && <p className="empty">No tickets match these filters.</p>}
        {data && data.items.map((ticket) => (
          <Link key={ticket.id} to={`/tickets/${ticket.id}`} className="ticket-row">
            <div>
              <div className="ticket-subject">#{ticket.id} {ticket.subject}</div>
              <div className="ticket-meta">
                <span>{ticket.customer_name}</span>
                <span>{formatAgo(ticket.created_at)}</span>
                {ticket.needs_review && <span>Needs review</span>}
                {ticket.department_confidence != null && <span>{percent(ticket.department_confidence, 0)} department confidence</span>}
              </div>
            </div>
            <div className="ticket-side">
              <DepartmentBadge department={ticket.routing_department} />
              <PriorityBadge value={ticket.routing_priority} />
              <SentimentBadge value={ticket.routing_sentiment} />
              <StatusBadge value={ticket.status} />
            </div>
          </Link>
        ))}
      </section>
      {data && (
        <div className="pager">
          <span className="muted">{data.total} tickets</span>
          <div className="button-row">
            <button className="button secondary" type="button" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>Previous</button>
            <span>Page {page} of {pageCount}</span>
            <button className="button secondary" type="button" disabled={page >= pageCount} onClick={() => update({ page: String(page + 1) })}>Next</button>
          </div>
        </div>
      )}

      {composer && (
        <div className="drawer-backdrop" onClick={() => setComposer(false)}>
          <form className="drawer" onClick={(event) => event.stopPropagation()} onSubmit={submitTicket}>
            <p className="kicker">New ticket</p>
            <h2>It will be classified on the way in.</h2>
            <button className="button ghost" type="button" onClick={() => setForm(EXAMPLE)}>Use an example</button>
            <label className="field">Customer name
              <input required value={form.customer_name} onChange={(event) => setForm({ ...form, customer_name: event.target.value })} />
            </label>
            <label className="field">Email
              <input required type="email" value={form.customer_email} onChange={(event) => setForm({ ...form, customer_email: event.target.value })} />
            </label>
            <label className="field">Subject
              <input required value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} />
            </label>
            <label className="field">What they wrote
              <textarea required value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} />
            </label>
            <div className="button-row">
              <button className="button accent" type="submit" disabled={saving}>{saving ? "Classifying…" : "Create and classify"}</button>
              <button className="button secondary" type="button" onClick={() => setComposer(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
