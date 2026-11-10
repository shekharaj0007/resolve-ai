import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { DepartmentBadge, PageHeader, PriorityBadge } from "../components/ui";
import { percent } from "../format";

const EXAMPLES = [
  "duplicate charge on the studio plan",
  "pen will not stay paired",
  "package marked delivered but nothing arrived",
  "refund still missing after I shipped it back",
  "suspicious login from a new city",
  "2FA codes are being rejected",
];

export default function Search() {
  const [params, setParams] = useSearchParams();
  const initial = params.get("q") || "";
  const [text, setText] = useState(initial);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const query = params.get("q") || "";
    setText(query);
    if (query.length < 2) {
      setData(null);
      return undefined;
    }
    let ignore = false;
    setLoading(true);
    api.search(query).then((next) => {
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
  }, [params]);

  return (
    <>
      <PageHeader
        kicker="Semantic search"
        title="Find the case that already has an answer."
        lede="The query and the tickets are embedded in the same space. Results are nearest neighbors, not just shared keywords."
      />
      <form
        className="search-hero"
        onSubmit={(event) => {
          event.preventDefault();
          setParams(text.trim() ? { q: text.trim() } : {});
        }}
      >
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Describe the customer's problem"
          aria-label="Search tickets"
        />
      </form>
      <div className="examples">
        {EXAMPLES.map((example) => (
          <button key={example} className="button ghost" type="button" onClick={() => setParams({ q: example })}>
            {example}
          </button>
        ))}
      </div>
      {error && <p className="error-text">{error}</p>}
      {loading && <p className="muted">Searching…</p>}
      {data && (
        <section className="card">
          <p className="card-title">{data.results.length} neighbors</p>
          {data.results.length === 0 && <p className="empty">Nothing close enough in the index.</p>}
          {data.results.map((item) => (
            <Link key={item.id} to={`/tickets/${item.id}`} className="result">
              <div className="result-top">
                <strong>#{item.id} {item.subject}</strong>
                <span>{percent(item.score, 0)} similar</span>
              </div>
              <div className="ticket-meta">
                <DepartmentBadge department={item.department} />
                <PriorityBadge value={item.priority} />
              </div>
              <p className="fine-print">{item.snippet}</p>
            </Link>
          ))}
        </section>
      )}
    </>
  );
}
