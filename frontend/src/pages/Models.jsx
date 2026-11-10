import { useEffect, useState } from "react";
import { api } from "../api";
import { PageHeader } from "../components/ui";
import { labelFor, percent } from "../format";

function Bars({ rows, valueKey }) {
  const max = Math.max(0.001, ...rows.map((row) => Number(row[valueKey]) || 0));
  return rows.map((row) => {
    const value = Number(row[valueKey]) || 0;
    const width = valueKey === "f1" ? value * 100 : (value / max) * 100;
    return (
      <div key={row.label || row.term} className="bar-row">
        <span>{labelFor(row.label || row.term)}</span>
        <span className="bar-track">
          <span className="bar-fill" style={{ width: `${Math.max(2, Math.min(100, width))}%` }} />
        </span>
        <span className="bar-value">{valueKey === "gain" ? value.toFixed(1) : percent(value)}</span>
      </div>
    );
  });
}

export default function Models() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.metrics().then(setMetrics).catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!metrics) return <p className="muted">Loading model scores…</p>;
  if (!metrics.ready) {
    return (
      <PageHeader
        kicker="Models"
        title="The pipelines are not trained yet."
        lede="Run python -m backend.scripts.bootstrap from the repo root."
      />
    );
  }

  const cards = [
    ["Department", "Word and bigram TF-IDF, then logistic regression. The top class becomes the queue.", metrics.department],
    ["Priority", "The same style of TF-IDF features, scored by XGBoost across low, medium, high, and urgent.", metrics.priority],
    ["Sentiment", "A separate TF-IDF and logistic regression pipeline so frustrated tickets surface faster.", metrics.sentiment],
  ];

  return (
    <>
      <PageHeader
        kicker="Models"
        title="Holdout macro-F1, not a production claim."
        lede={metrics.dataset?.note}
      />
      <section className="model-grid">
        {cards.map(([title, blurb, block]) => (
          <article key={title} className="card">
            <p className="card-title">{block.algorithm}</p>
            <h2>{title}</h2>
            <p className="lede">{blurb}</p>
            <p className="stat-value" style={{ marginTop: 12 }}>{percent(block.macro_f1)}</p>
            <p className="stat-label">macro-F1 · target {percent(metrics.target_macro_f1, 0)}</p>
            <p className="fine-print">
              Accuracy {percent(block.accuracy)} on {block.test_size} holdout tickets. Trained on {block.train_size}.
            </p>
            <Bars rows={block.per_class} valueKey="f1" />
          </article>
        ))}
      </section>

      <section className="grid-2" style={{ marginTop: 12 }}>
        <article className="card">
          <p className="card-title">Terms the linear models lean on</p>
          {[metrics.department, metrics.sentiment].filter((block) => block.terms).map((block) => (
            <div key={block.algorithm + block.macro_f1}>
              {block.terms.map((row) => (
                <p key={row.label} className="fine-print">
                  <strong>{labelFor(row.label)}.</strong> {row.terms.join(", ")}
                </p>
              ))}
            </div>
          ))}
        </article>
        <article className="card">
          <p className="card-title">Embeddings</p>
          <h2 style={{ fontSize: 28 }}>{metrics.embedder?.name || "Not recorded yet"}</h2>
          <p className="lede">
            {metrics.embedder
              ? `${metrics.embedder.dim}-dimension vectors. Search ranks tickets by cosine similarity.`
              : "Run bootstrap to record which embedder built the index."}
          </p>
          {metrics.embedder && !String(metrics.embedder.name).includes("sentence-transformers") && (
            <p className="fine-print">
              Install requirements-embeddings.txt and run bootstrap again to switch search to all-MiniLM-L6-v2.
            </p>
          )}
          {metrics.priority.top_features && (
            <>
              <p className="card-title" style={{ marginTop: 16 }}>Priority splits the trees on</p>
              <Bars rows={metrics.priority.top_features} valueKey="gain" />
            </>
          )}
        </article>
      </section>
    </>
  );
}
