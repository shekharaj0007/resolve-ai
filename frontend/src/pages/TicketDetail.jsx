import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAgent } from "../components/Shell";
import { DepartmentBadge, Meter, PageHeader, PriorityBadge, SentimentBadge, StatusBadge } from "../components/ui";
import { formatAgo, initials, labelFor, minutes, percent } from "../format";

const STATUSES = ["open", "triaged", "in_progress", "pending_customer", "resolved"];

export default function TicketDetail() {
  const { id } = useParams();
  const { agent } = useAgent();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [department, setDepartment] = useState("");
  const [priority, setPriority] = useState("medium");
  const [sentiment, setSentiment] = useState("neutral");
  const [draft, setDraft] = useState("");
  const [departments, setDepartments] = useState([]);

  useEffect(() => {
    let ignore = false;
    setData(null);
    api.departments().then((rows) => {
      if (!ignore) setDepartments(rows);
    }).catch(() => {});
    api.ticket(id).then((next) => {
      if (!ignore) setData(next);
    }).catch((err) => {
      if (!ignore) setError(err.message);
    });
    return () => {
      ignore = true;
    };
  }, [id]);

  const ticket = data?.ticket;

  useEffect(() => {
    if (!ticket) return;
    setDepartment(ticket.final_department?.slug || ticket.predicted_department?.slug || "");
    setPriority(ticket.routing_priority || "medium");
    setSentiment(ticket.routing_sentiment || "neutral");
    setDraft(ticket.suggested_reply || "");
  }, [ticket?.id]);

  useEffect(() => {
    if (ticket?.suggested_reply) setDraft(ticket.suggested_reply);
  }, [ticket?.id, ticket?.suggested_reply]);

  async function run(action, fn) {
    setBusy(action);
    setError("");
    try {
      setData(await fn());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  if (error && !ticket) return <p className="error-text">{error}</p>;
  if (!ticket) return <p className="muted">Loading ticket…</p>;

  const scores = ticket.scores || {};
  const usedSuggestion = Boolean(draft.trim() && ticket.suggested_reply && draft.trim() === ticket.suggested_reply.trim());

  return (
    <>
      <PageHeader kicker={`Ticket #${ticket.id}`} title={ticket.subject} lede={`${ticket.customer_name} · ${ticket.customer_email} · ${formatAgo(ticket.created_at)}`}>
        <label className="field">
          Status
          <select
            className="inline-select"
            value={ticket.status}
            onChange={(event) => run("status", () => api.setStatus(ticket.id, event.target.value))}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>{labelFor(status)}</option>
            ))}
          </select>
        </label>
      </PageHeader>

      {error && <p className="error-text" style={{ marginBottom: 12 }}>{error}</p>}

      <div className="detail-grid">
        <section className="card thread">
          <div className="ticket-side" style={{ justifyContent: "flex-start" }}>
            <StatusBadge value={ticket.status} />
            <DepartmentBadge department={ticket.routing_department} />
            <PriorityBadge value={ticket.routing_priority} />
            <SentimentBadge value={ticket.routing_sentiment} />
            {ticket.needs_review && <span className="badge warn">Needs review</span>}
          </div>
          {(ticket.messages || []).map((message) => (
            <article key={message.id} className={`message ${message.author_type}`}>
              <div className="avatar">{initials(message.author_name)}</div>
              <div>
                <header>
                  <strong>{message.author_name}</strong>
                  <span>{message.author_type === "agent" ? "Agent" : "Customer"} · {formatAgo(message.created_at)}</span>
                </header>
                <div className="message-body">{message.body}</div>
              </div>
            </article>
          ))}
        </section>

        <aside className="ai-panel">
          <section className="card">
            <p className="card-title">Routing recommendation</p>
            <div className="score-line">
              <DepartmentBadge department={ticket.predicted_department} />
              <strong>{percent(ticket.department_confidence, 0)}</strong>
            </div>
            <Meter value={ticket.department_confidence} />
            <p className="fine-print">Routes to {ticket.predicted_department?.queue_name || "a queue"}.</p>
            {(scores.department || []).slice(0, 3).map((row) => (
              <div key={row.label} className="bar-row">
                <span>{labelFor(row.label)}</span>
                <span className="bar-track"><span className="bar-fill" style={{ width: percent(row.score, 0) }} /></span>
                <span className="bar-value">{percent(row.score, 0)}</span>
              </div>
            ))}
            <div className="score-line">
              <span>Priority</span>
              <PriorityBadge value={ticket.predicted_priority} />
              <span>{percent(ticket.priority_confidence, 0)}</span>
            </div>
            <div className="score-line">
              <span>Sentiment</span>
              <SentimentBadge value={ticket.predicted_sentiment} />
              <span>{percent(ticket.sentiment_confidence, 0)}</span>
            </div>
            {scores.terms?.length > 0 && (
              <div className="term-list">
                {scores.terms.map((term) => (
                  <span key={term.term} className="term">{term.term}</span>
                ))}
              </div>
            )}
            {ticket.validation_action === "corrected" && (
              <p className="fine-print">Corrected by {ticket.validated_by}. The original prediction stays on this card.</p>
            )}
            {ticket.validation_action === "accepted" && (
              <p className="fine-print">Accepted by {ticket.validated_by}.</p>
            )}
            <div className="button-row">
              <button
                className="button accent"
                type="button"
                disabled={busy !== "" || !ticket.predicted_department}
                onClick={() => {
                  setDepartment(ticket.predicted_department.slug);
                  setPriority(ticket.predicted_priority);
                  setSentiment(ticket.predicted_sentiment);
                  run("accept", () => api.validate(ticket.id, {
                    department: ticket.predicted_department.slug,
                    priority: ticket.predicted_priority,
                    sentiment: ticket.predicted_sentiment,
                    agent,
                  }));
                }}
              >
                {busy === "accept" ? "Saving…" : "Accept routing"}
              </button>
            </div>
          </section>

          <section className="card">
            <p className="card-title">Active labels</p>
            <label className="field">Queue
              <select value={department} onChange={(event) => setDepartment(event.target.value)}>
                {departments.map((item) => (
                  <option key={item.slug} value={item.slug}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="field">Priority
              <select value={priority} onChange={(event) => setPriority(event.target.value)}>
                {["low", "medium", "high", "urgent"].map((item) => (
                  <option key={item} value={item}>{labelFor(item)}</option>
                ))}
              </select>
            </label>
            <label className="field">Sentiment
              <select value={sentiment} onChange={(event) => setSentiment(event.target.value)}>
                {["negative", "neutral", "positive"].map((item) => (
                  <option key={item} value={item}>{labelFor(item)}</option>
                ))}
              </select>
            </label>
            <div className="button-row">
              <button
                className="button secondary"
                type="button"
                disabled={busy !== ""}
                onClick={() => run("correct", () => api.validate(ticket.id, { department, priority, sentiment, agent }))}
              >
                {busy === "correct" ? "Saving…" : "Save correction"}
              </button>
            </div>
          </section>

          <section className="card">
            <p className="card-title">Similar tickets</p>
            {(data.similar || []).length === 0 && <p className="muted">No close neighbor yet.</p>}
            <div className="similar">
              {(data.similar || []).map((item) => (
                <Link key={item.id} to={`/tickets/${item.id}`}>
                  <strong>#{item.id} {item.subject}</strong>
                  <div className="ticket-meta">
                    <span>{percent(item.score, 0)} similar</span>
                    {item.department && <span>{item.department.name}</span>}
                  </div>
                  {item.resolution && <p className="clamp fine-print">{item.resolution}</p>}
                </Link>
              ))}
            </div>
          </section>

          <section className="card">
            <p className="card-title">Suggested reply</p>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Generate a draft from the policy and similar tickets." />
            <p className="fine-print">
              {ticket.suggestion_source === "llm"
                ? "Drafted by the configured LLM. Review it before sending."
                : "Drafted from the department policy and similar resolved tickets. An agent has to send it."}
              {" "}Manual baseline for this ticket is {minutes(ticket.baseline_seconds)}.
              {ticket.used_ai_reply && ticket.assisted_seconds
                ? ` Assisted time recorded at ${minutes(ticket.assisted_seconds)}.`
                : " Sending this draft records the assisted time."}
            </p>
            <div className="button-row">
              <button className="button secondary" type="button" disabled={busy !== ""} onClick={() => run("draft", () => api.suggest(ticket.id))}>
                {busy === "draft" ? "Drafting…" : "Generate draft"}
              </button>
              <button
                className="button"
                type="button"
                disabled={busy !== "" || draft.trim().length < 2}
                onClick={() => run("send", () => api.reply(ticket.id, {
                  body: draft.trim(),
                  agent,
                  used_suggestion: usedSuggestion,
                  resolve: false,
                  department,
                  priority,
                  sentiment,
                }))}
              >
                {busy === "send" ? "Sending…" : "Send reply"}
              </button>
              <button
                className="button accent"
                type="button"
                disabled={busy !== "" || draft.trim().length < 2}
                onClick={() => run("resolve", () => api.reply(ticket.id, {
                  body: draft.trim(),
                  agent,
                  used_suggestion: usedSuggestion,
                  resolve: true,
                  department,
                  priority,
                  sentiment,
                }))}
              >
                Send and resolve
              </button>
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
