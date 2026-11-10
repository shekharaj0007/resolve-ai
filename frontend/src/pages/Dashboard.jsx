import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { PageHeader } from "../components/ui";
import { DepartmentBadge, PriorityBadge } from "../components/ui";
import { formatAgo, labelFor, minutes, percent } from "../format";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    api.analytics().then((next) => {
      if (!ignore) setData(next);
    }).catch((err) => {
      if (!ignore) setError(err.message);
    });
    return () => {
      ignore = true;
    };
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p className="muted">Loading the queue…</p>;

  const totals = data.totals;
  const maxDept = Math.max(1, ...data.by_department.map((row) => row.count));
  const maxVolume = Math.max(1, ...data.volume_by_day.map((row) => row.count));

  return (
    <>
      <PageHeader
        kicker="Queue overview"
        title="Fieldnote support, routed before anyone opens the ticket."
        lede="Classification, priority, and sentiment land on every ticket. An agent accepts or corrects the routing, then sends the draft."
      >
        <Link className="button" to="/inbox">Open the queue</Link>
      </PageHeader>

      {totals.tickets === 0 ? (
        <div className="card empty">
          The queue is empty. Run <strong>python -m backend.scripts.bootstrap</strong> to train the pipelines and load the corpus.
        </div>
      ) : (
        <>
          <section className="stats">
            <Link className="stat stat-link" to="/inbox?review=needs">
              <span className="stat-value">{totals.needs_review}</span>
              <span className="stat-label">Need review</span>
              <span className="stat-note">{totals.active} still open in the queue</span>
            </Link>
            <Link className="stat stat-link" to="/models">
              <span className="stat-value">{percent(data.models.department_macro_f1)}</span>
              <span className="stat-label">Department macro-F1</span>
              <span className="stat-note">Holdout score. Target 85%.</span>
            </Link>
            <article className="stat">
              <span className="stat-value">{totals.reduction_pct == null ? "—" : `${totals.reduction_pct}%`}</span>
              <span className="stat-label">Projected reduction</span>
              <span className="stat-note">
                {minutes(totals.assisted_seconds_median)} assisted vs {minutes(totals.baseline_seconds_median)} baseline
              </span>
            </article>
            <Link className="stat stat-link" to="/inbox?review=corrected">
              <span className="stat-value">{percent(totals.holdout_agreement)}</span>
              <span className="stat-label">Holdout labels kept</span>
              <span className="stat-note">{totals.corrected} corrections across the whole queue</span>
            </Link>
          </section>

          <section className="grid-2">
            <article className="card">
              <p className="card-title">Volume by queue</p>
              {data.by_department.map((row) => (
                <Link key={row.slug} to={`/inbox?department=${row.slug}&review=all`} className="bar-row">
                  <span>{row.name}</span>
                  <span className="bar-track"><span className="bar-fill" style={{ width: `${(row.count / maxDept) * 100}%` }} /></span>
                  <span className="bar-value">{row.count}</span>
                </Link>
              ))}
            </article>
            <article className="card">
              <p className="card-title">Priority and tone</p>
              {data.by_priority.map((row) => (
                <div key={row.label} className="bar-row">
                  <span>{labelFor(row.label)}</span>
                  <span className="bar-track"><span className="bar-fill info" style={{ width: `${(row.count / totals.tickets) * 100}%` }} /></span>
                  <span className="bar-value">{row.count}</span>
                </div>
              ))}
              <div style={{ height: 10 }} />
              {data.by_sentiment.map((row) => (
                <div key={row.label} className="bar-row">
                  <span>{labelFor(row.label)}</span>
                  <span className="bar-track"><span className="bar-fill good" style={{ width: `${(row.count / totals.tickets) * 100}%` }} /></span>
                  <span className="bar-value">{row.count}</span>
                </div>
              ))}
            </article>
          </section>

          <section className="card" style={{ marginBottom: 12 }}>
            <p className="card-title">Arrivals, last 14 days</p>
            <div className="volume">
              {data.volume_by_day.map((day, index) => (
                <div key={day.date} className="volume-col" title={`${day.date}: ${day.count}`}>
                  <span style={{ height: `${Math.max(6, (day.count / maxVolume) * 100)}%` }} />
                  <em>{index === 0 || index === data.volume_by_day.length - 1 ? day.date.slice(5) : ""}</em>
                </div>
              ))}
            </div>
            <p className="fine-print">{data.handling_time_note}</p>
          </section>

          <section className="card list-card">
            <p className="card-title">Latest tickets</p>
            {data.recent.map((ticket) => (
              <Link key={ticket.id} to={`/tickets/${ticket.id}`} className="ticket-row">
                <div>
                  <div className="ticket-subject">#{ticket.id} {ticket.subject}</div>
                  <div className="ticket-meta">
                    <span>{ticket.customer_name}</span>
                    <span>{formatAgo(ticket.created_at)}</span>
                  </div>
                </div>
                <div className="ticket-side">
                  <DepartmentBadge department={ticket.routing_department} />
                  <PriorityBadge value={ticket.routing_priority} />
                </div>
              </Link>
            ))}
          </section>
        </>
      )}
    </>
  );
}
