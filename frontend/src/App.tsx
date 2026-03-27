/**
 * Main UI: ranked KOL channels from the FastAPI backend.
 * Dev server proxies /api and /health to the backend (see vite.config.ts).
 */
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import "./App.css";

const CONTACT_COL_STORAGE_KEY = "hunter-contact-col-px";
const CONTACT_COL_DEFAULT = 320;
const CONTACT_COL_MIN = 200;
const CONTACT_COL_MAX = 520;

function readStoredContactColPx(): number {
  try {
    const s = localStorage.getItem(CONTACT_COL_STORAGE_KEY);
    const n = s ? parseInt(s, 10) : NaN;
    if (Number.isFinite(n) && n >= CONTACT_COL_MIN && n <= CONTACT_COL_MAX) return n;
  } catch {
    /* ignore */
  }
  return CONTACT_COL_DEFAULT;
}

/** One row from GET /api/kols (matches backend KolOut). */
type Kol = {
  channel_id: string;
  title: string;
  description: string;
  custom_url: string | null;
  subscriber_count: number | null;
  video_count: number | null;
  thumbnail_url: string | null;
  topic: string;
  score: number;
  youtube_url: string;
  contact_detail: string;
};

function topicPillClass(topic: string): string {
  if (topic === "football_equipment") return "pill pill--equip";
  if (topic === "smart_wearables") return "pill pill--wear";
  return "pill";
}

function topicLabel(topic: string): string {
  if (topic === "football_equipment") return "Football equipment";
  if (topic === "smart_wearables") return "Smart wearables";
  return topic;
}

/** One segment: URL, mailto email, or plain text (e.g. /about fallback). */
function ContactPart({ part }: { part: string }) {
  const p = part.trim();
  if (!p) return null;
  if (/^https?:\/\//i.test(p)) {
    const display = p.length > 48 ? `${p.slice(0, 46)}…` : p;
    return (
      <a className="contact-link" href={p} target="_blank" rel="noreferrer" title={p}>
        {display}
      </a>
    );
  }
  if (p.includes("@") && !/\s/.test(p)) {
    return (
      <a className="contact-link" href={`mailto:${p}`}>
        {p}
      </a>
    );
  }
  return <span className="contact-text">{p}</span>;
}

/** contact_detail from API: emails and/or URLs, joined with " · "; empty → em dash. */
function ContactCell({ value }: { value: string }) {
  const v = value?.trim() ?? "";
  if (!v) return <span className="contact-muted">—</span>;
  const parts = v.split(/\s*·\s*/).filter(Boolean);
  if (parts.length === 0) return <span className="contact-muted">—</span>;
  return (
    <span className="contact-multi">
      {parts.map((part, i) => (
        <Fragment key={`${i}-${part.slice(0, 24)}`}>
          {i > 0 ? <span className="contact-sep"> · </span> : null}
          <ContactPart part={part} />
        </Fragment>
      ))}
    </span>
  );
}

function ChannelThumb({ url, title }: { url: string | null; title: string }) {
  const [broken, setBroken] = useState(false);
  const initial = (title.trim().charAt(0) || "?").toUpperCase();

  if (!url || broken) {
    return (
      <div className="channel-thumb channel-thumb--placeholder" aria-hidden title={title}>
        {initial}
      </div>
    );
  }

  return (
    <img
      className="channel-thumb"
      src={url}
      alt=""
      width={44}
      height={44}
      loading="lazy"
      onError={() => setBroken(true)}
    />
  );
}

function apiHealthBadge(health: string): { className: string; label: string; title: string } {
  const down = /offline|error|fail/i.test(health) || health === "…";
  if (!down) {
    try {
      const j = JSON.parse(health) as { status?: string };
      if (j.status === "ok") {
        return {
          className: "health-badge health-badge--ok",
          label: "Connected",
          title: health,
        };
      }
    } catch {
      /* not JSON */
    }
  }
  if (down) {
    return { className: "health-badge health-badge--down", label: health, title: health };
  }
  return { className: "health-badge", label: health, title: health };
}

export default function App() {
  const [health, setHealth] = useState<string>("…");
  const [topic, setTopic] = useState<string>("all");
  const [searchText, setSearchText] = useState<string>("");
  const [sort, setSort] = useState<string>("score");
  const [kols, setKols] = useState<Kol[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [contactColPx, setContactColPx] = useState(() =>
    typeof window !== "undefined" ? readStoredContactColPx() : CONTACT_COL_DEFAULT,
  );

  useEffect(() => {
    try {
      localStorage.setItem(CONTACT_COL_STORAGE_KEY, String(contactColPx));
    } catch {
      /* ignore */
    }
  }, [contactColPx]);

  const appStyle = useMemo(
    () =>
      ({
        "--contact-col": `${contactColPx}px`,
      }) as CSSProperties,
    [contactColPx],
  );

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    p.set("sort", sort);
    p.set("limit", "200");
    if (topic !== "all") p.set("topic", topic);
    const q = searchText.trim();
    if (q) p.set("search", q);
    return p.toString();
  }, [topic, sort, searchText]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await fetch(`/api/kols?${qs}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = (await r.json()) as Kol[];
      setKols(Array.isArray(data) ? data : []);
    } catch (e) {
      setKols([]);
      setError(e instanceof Error ? e.message : "Failed to load KOLs");
    }
  }, [qs]);

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((j) => setHealth(JSON.stringify(j)))
      .catch(() => setHealth("backend offline (start uvicorn on :8000)"));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const csvHref = `/api/kols/export.csv?${qs}`;
  const badge = apiHealthBadge(health);

  return (
    <div className="app" style={appStyle}>
      <header className="header">
        <div className="brand">
          <h1 className="logo">
            hunt<span>er</span>
          </h1>
          <p className="tagline">
            Discover YouTube voices in <strong>football equipment</strong> and{" "}
            <strong>smart wearables</strong> — ranked by relevance and reach.
          </p>
        </div>
        <div className="health-panel">
          <span className="health-label">API status</span>
          <span className={badge.className} title={badge.title}>
            <span className="health-dot" aria-hidden />
            {badge.label.length > 40 ? `${badge.label.slice(0, 38)}…` : badge.label}
          </span>
        </div>
      </header>

      <section className="toolbar" aria-label="Filters and export">
        <label className="field">
          <span>Topic</span>
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="all">All topics</option>
            <option value="football_equipment">Football equipment</option>
            <option value="smart_wearables">Smart wearables</option>
          </select>
        </label>
        <label className="field field--search">
          <span>Search</span>
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Channel or video text…"
            maxLength={200}
            autoComplete="off"
          />
        </label>
        <label className="field">
          <span>Sort by</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="score">Score</option>
            <option value="subscribers">Subscribers</option>
            <option value="title">Channel name</option>
            <option value="contact">Contact (email)</option>
          </select>
        </label>
        <label className="field field--range">
          <span>Contact column width</span>
          <div className="field-range-row">
            <input
              type="range"
              min={CONTACT_COL_MIN}
              max={CONTACT_COL_MAX}
              step={10}
              value={contactColPx}
              onChange={(e) => setContactColPx(Number(e.target.value))}
              aria-valuemin={CONTACT_COL_MIN}
              aria-valuemax={CONTACT_COL_MAX}
              aria-valuenow={contactColPx}
            />
            <span className="field-range-value">{contactColPx}px</span>
          </div>
        </label>
        <div className="toolbar-actions">
          <button type="button" className="btn btn-ghost" onClick={() => void load()}>
            Refresh
          </button>
          <a className="btn btn-primary" href={csvHref} download>
            Download CSV
          </a>
        </div>
      </section>

      {error ? <p className="err">{error}</p> : null}

      <div className="table-wrap">
        <table className="kols">
          <thead>
            <tr>
              <th>#</th>
              <th>Channel</th>
              <th className="col-contact">Contact</th>
              <th className="num">Score</th>
              <th className="num">Subs</th>
              <th>Topic</th>
              <th className="col-youtube-url">YouTube URL</th>
              <th>Open</th>
            </tr>
          </thead>
          <tbody>
            {kols.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty">
                  No channels yet. Run{" "}
                  <code>hunter discover --topic football_equipment</code> with{" "}
                  <code>YOUTUBE_API_KEY</code> in <code>backend/.env</code>, then refresh.
                </td>
              </tr>
            ) : (
              kols.map((k, i) => (
                <tr key={`${k.channel_id}-${k.topic}`}>
                  <td className="num">{i + 1}</td>
                  <td>
                    <div className="channel-cell">
                      <ChannelThumb url={k.thumbnail_url} title={k.title} />
                      <div className="channel-text">
                        <div className="title">{k.title}</div>
                        {k.youtube_url ? (
                          <div className="channel-youtube-url">
                            <span className="channel-youtube-label">youtube_url</span>
                            <a
                              className="channel-youtube-link"
                              href={k.youtube_url}
                              target="_blank"
                              rel="noreferrer"
                              title={k.youtube_url}
                            >
                              {k.youtube_url}
                            </a>
                          </div>
                        ) : null}
                        {k.description ? (
                          <div className="desc" title={k.description}>
                            {k.description}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </td>
                  <td className="contact col-contact">
                    <ContactCell value={k.contact_detail ?? ""} />
                  </td>
                  <td className="num num--score">{k.score.toFixed(2)}</td>
                  <td className="num">
                    {k.subscriber_count != null ? k.subscriber_count.toLocaleString() : "—"}
                  </td>
                  <td>
                    <span className={topicPillClass(k.topic)}>{topicLabel(k.topic)}</span>
                  </td>
                  <td className="url-cell col-youtube-url">
                    {k.youtube_url ? (
                      <a
                        className="url-link"
                        href={k.youtube_url}
                        target="_blank"
                        rel="noreferrer"
                        title={k.youtube_url}
                      >
                        {k.youtube_url}
                      </a>
                    ) : (
                      <span className="contact-muted">—</span>
                    )}
                  </td>
                  <td>
                    {k.youtube_url ? (
                      <a className="link-yt" href={k.youtube_url} target="_blank" rel="noreferrer">
                        <span className="link-yt-icon" aria-hidden>
                          ▶
                        </span>
                        YouTube
                      </a>
                    ) : (
                      <span className="contact-muted">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <footer className="app-footer">
        Data from YouTube Data API v3 · hunter
      </footer>
    </div>
  );
}
