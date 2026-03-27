/**
 * Main UI: ranked KOL channels from the FastAPI backend.
 * Dev server proxies /api and /health to the backend (see vite.config.ts).
 */
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
  return topic.replace(/_/g, " ");
}

/** GET /api/topics row */
type TopicRow = {
  topic: string;
  query_count: number;
  queries: string[];
};

const TOPIC_SLUG_RE = /^[a-z0-9_]{1,64}$/;

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
  const [topicRows, setTopicRows] = useState<TopicRow[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(true);
  const [topicsError, setTopicsError] = useState<string | null>(null);
  const [manageTopicsOpen, setManageTopicsOpen] = useState(false);
  const [formTopicSlug, setFormTopicSlug] = useState("");
  const [formQueriesText, setFormQueriesText] = useState("");
  const [formSaving, setFormSaving] = useState(false);
  const [formSlugReadOnly, setFormSlugReadOnly] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [discoverBusy, setDiscoverBusy] = useState(false);
  const [discoverBanner, setDiscoverBanner] = useState<string | null>(null);
  const [discPollTopic, setDiscPollTopic] = useState<string | null>(null);
  const [searchText, setSearchText] = useState<string>("");
  const [sort, setSort] = useState<string>("score");
  const [kols, setKols] = useState<Kol[]>([]);
  const [kolsLoading, setKolsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contactColPx, setContactColPx] = useState(() =>
    typeof window !== "undefined" ? readStoredContactColPx() : CONTACT_COL_DEFAULT,
  );

  const tableScrollRef = useRef<HTMLDivElement>(null);
  const tableHScrollBarRef = useRef<HTMLDivElement>(null);
  const ignoreMainScroll = useRef(false);
  const ignoreSyncScroll = useRef(false);
  const [tableSyncScrollWidth, setTableSyncScrollWidth] = useState(0);
  const [tableNeedsHScroll, setTableNeedsHScroll] = useState(false);

  useLayoutEffect(() => {
    const main = tableScrollRef.current;
    if (!main) return;

    const pushMetrics = () => {
      const sw = main.scrollWidth;
      const cw = main.clientWidth;
      setTableSyncScrollWidth(sw);
      setTableNeedsHScroll(sw > cw);
      const sync = tableHScrollBarRef.current;
      if (sync) {
        ignoreSyncScroll.current = true;
        sync.scrollLeft = main.scrollLeft;
        requestAnimationFrame(() => {
          ignoreSyncScroll.current = false;
        });
      }
    };

    pushMetrics();

    const onMainScroll = () => {
      if (ignoreMainScroll.current) return;
      const sync = tableHScrollBarRef.current;
      if (!sync) return;
      ignoreSyncScroll.current = true;
      sync.scrollLeft = main.scrollLeft;
      requestAnimationFrame(() => {
        ignoreSyncScroll.current = false;
      });
    };

    main.addEventListener("scroll", onMainScroll, { passive: true });
    const ro = new ResizeObserver(() => pushMetrics());
    ro.observe(main);
    const table = main.querySelector("table");
    if (table) ro.observe(table);

    return () => {
      ro.disconnect();
      main.removeEventListener("scroll", onMainScroll);
    };
  }, [kols.length, contactColPx, topic, sort, searchText]);

  useLayoutEffect(() => {
    if (!tableNeedsHScroll) return;
    const sync = tableHScrollBarRef.current;
    const main = tableScrollRef.current;
    if (!sync || !main) return;

    const onSyncScroll = () => {
      if (ignoreSyncScroll.current) return;
      ignoreMainScroll.current = true;
      main.scrollLeft = sync.scrollLeft;
      requestAnimationFrame(() => {
        ignoreMainScroll.current = false;
      });
    };

    ignoreSyncScroll.current = true;
    sync.scrollLeft = main.scrollLeft;
    requestAnimationFrame(() => {
      ignoreSyncScroll.current = false;
    });

    sync.addEventListener("scroll", onSyncScroll, { passive: true });
    return () => sync.removeEventListener("scroll", onSyncScroll);
  }, [tableNeedsHScroll, tableSyncScrollWidth, kols.length, contactColPx]);

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

  const pingHealth = useCallback(() => {
    fetch("/health", { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => setHealth(JSON.stringify(j)))
      .catch(() => setHealth("backend offline (start uvicorn on :8000)"));
  }, []);

  const loadKols = useCallback(async () => {
    setError(null);
    setKolsLoading(true);
    try {
      const r = await fetch(`/api/kols?${qs}`, { cache: "no-store" });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = (await r.json()) as Kol[];
      setKols(Array.isArray(data) ? data : []);
    } catch (e) {
      setKols([]);
      setError(e instanceof Error ? e.message : "Failed to load KOLs");
    } finally {
      setKolsLoading(false);
    }
  }, [qs]);

  const refresh = useCallback(() => {
    pingHealth();
    void loadKols();
  }, [pingHealth, loadKols]);

  const loadTopics = useCallback(async () => {
    setTopicsError(null);
    setTopicsLoading(true);
    try {
      const r = await fetch("/api/topics", { cache: "no-store" });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = (await r.json()) as TopicRow[];
      setTopicRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setTopicRows([]);
      setTopicsError(e instanceof Error ? e.message : "Failed to load topics");
    } finally {
      setTopicsLoading(false);
    }
  }, []);

  useEffect(() => {
    pingHealth();
  }, [pingHealth]);

  useEffect(() => {
    void loadTopics();
  }, [loadTopics]);

  useEffect(() => {
    void loadKols();
  }, [loadKols]);

  useEffect(() => {
    if (topic === "all") return;
    if (!topicRows.length) return;
    if (!topicRows.some((t) => t.topic === topic)) {
      setTopic("all");
    }
  }, [topic, topicRows]);

  useEffect(() => {
    if (!discPollTopic) return;
    const tick = async () => {
      try {
        const r = await fetch("/api/discover/status?limit=15", { cache: "no-store" });
        if (!r.ok) return;
        const rows = (await r.json()) as {
          topic: string;
          finished_at: string | null;
          videos_upserted: number;
          channels_upserted: number;
        }[];
        const mine = rows.find((x) => x.topic === discPollTopic && x.finished_at);
        if (mine) {
          setDiscoverBanner(
            `Discovery finished for ${discPollTopic}: ${mine.videos_upserted} videos, ${mine.channels_upserted} channels.`,
          );
          setDiscPollTopic(null);
          void loadKols();
        }
      } catch {
        /* ignore */
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 4000);
    return () => window.clearInterval(id);
  }, [discPollTopic, loadKols]);

  const openNewTopicForm = () => {
    setFormError(null);
    setFormSlugReadOnly(false);
    setFormTopicSlug("");
    setFormQueriesText("");
    setManageTopicsOpen(true);
  };

  const openEditTopicForm = (slug: string) => {
    const row = topicRows.find((t) => t.topic === slug);
    setFormError(null);
    setFormSlugReadOnly(true);
    setFormTopicSlug(slug);
    setFormQueriesText(row ? row.queries.join("\n") : "");
    setManageTopicsOpen(true);
  };

  const saveTopicForm = async () => {
    setFormError(null);
    const slug = formTopicSlug.trim();
    if (!TOPIC_SLUG_RE.test(slug)) {
      setFormError("Topic key must be 1–64 chars: lowercase letters, digits, underscore only.");
      return;
    }
    const lines = formQueriesText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) {
      setFormError("Add at least one search query (one per line).");
      return;
    }
    setFormSaving(true);
    try {
      const r = await fetch(`/api/topics/${encodeURIComponent(slug)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queries: lines }),
      });
      if (!r.ok) {
        const errBody = await r.json().catch(() => ({}));
        const detail =
          typeof errBody === "object" && errBody && "detail" in errBody
            ? String((errBody as { detail: unknown }).detail)
            : `${r.status}`;
        throw new Error(detail);
      }
      setManageTopicsOpen(false);
      await loadTopics();
      setTopic(slug);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setFormSaving(false);
    }
  };

  const deleteTopic = async (slug: string) => {
    if (!window.confirm(`Delete topic "${slug}"? Fails if channels still use it.`)) return;
    setFormError(null);
    try {
      const r = await fetch(`/api/topics/${encodeURIComponent(slug)}`, { method: "DELETE" });
      if (!r.ok) {
        const errBody = await r.json().catch(() => ({}));
        const detail =
          typeof errBody === "object" && errBody && "detail" in errBody
            ? String((errBody as { detail: unknown }).detail)
            : `${r.status}`;
        throw new Error(detail);
      }
      setManageTopicsOpen(false);
      await loadTopics();
      if (topic === slug) setTopic("all");
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const runDiscovery = async () => {
    if (topic === "all") return;
    setDiscoverBanner(null);
    setDiscoverBusy(true);
    try {
      const r = await fetch("/api/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic }),
      });
      if (!r.ok) {
        const errBody = await r.json().catch(() => ({}));
        const detail =
          typeof errBody === "object" && errBody && "detail" in errBody
            ? String((errBody as { detail: unknown }).detail)
            : `${r.status}`;
        throw new Error(detail);
      }
      setDiscoverBanner(`Discovery started for “${topic}”. This runs in the background; the table will refresh when it completes.`);
      setDiscPollTopic(topic);
    } catch (e) {
      setDiscoverBanner(e instanceof Error ? e.message : "Discovery request failed");
    } finally {
      setDiscoverBusy(false);
    }
  };

  const csvHref = `/api/kols/export.csv?${qs}`;
  const badge = apiHealthBadge(health);

  return (
    <div
      className={`app${tableNeedsHScroll ? " app--table-hscroll-dock" : ""}`}
      style={appStyle}
    >
      <header className="header">
        <div className="brand">
          <h1 className="logo">
            HUNT<span>ER</span>
          </h1>
          <p className="tagline">
            Discover YouTube KOLs by configurable topics — search queries live in the database
            (seeded from defaults). Manage topics and run discovery from the toolbar.
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
          <select
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            disabled={topicsLoading}
          >
            <option value="all">All topics</option>
            {topicRows.map((t) => (
              <option key={t.topic} value={t.topic}>
                {topicLabel(t.topic)} ({t.query_count} queries)
              </option>
            ))}
          </select>
        </label>
        <div className="toolbar-topic-actions">
          <button type="button" className="btn btn-ghost btn--sm" onClick={() => void loadTopics()}>
            Reload topics
          </button>
          <button type="button" className="btn btn-ghost btn--sm" onClick={openNewTopicForm}>
            Manage topics
          </button>
          <button
            type="button"
            className="btn btn-ghost btn--sm"
            onClick={() => void runDiscovery()}
            disabled={discoverBusy || topic === "all" || topicsLoading}
            title={topic === "all" ? "Select a single topic first" : "Run YouTube discovery for this topic"}
          >
            {discoverBusy ? "Starting…" : "Run discovery"}
          </button>
        </div>
        <label className="field field--search">
          <span>Local filter</span>
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
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => refresh()}
            disabled={kolsLoading}
          >
            {kolsLoading ? "Refreshing…" : "Refresh"}
          </button>
          <a className="btn btn-primary" href={csvHref} download>
            Download CSV
          </a>
        </div>
      </section>

      <p
        className="results-bar"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span className="results-bar__count">{kols.length}</span>
        {kols.length === 1 ? " channel" : " channels"} shown
      </p>

      {topicsError ? <p className="err">{topicsError}</p> : null}
      {discoverBanner ? <p className="banner banner--info">{discoverBanner}</p> : null}
      {error ? <p className="err">{error}</p> : null}

      <div className="table-panel">
        <div className="table-wrap" ref={tableScrollRef}>
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
                    No channels yet. Select a topic and click <strong>Run discovery</strong>, or run{" "}
                    <code>hunter discover --topic …</code> with <code>YOUTUBE_API_KEY</code> in{" "}
                    <code>backend/.env</code>, then refresh.
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
      </div>

      {tableNeedsHScroll ? (
        <div className="table-hscroll-dock" role="region" aria-label="Channel table horizontal scroll">
          <div className="table-hscroll-dock__align">
            <div className="table-hscroll-dock__track" ref={tableHScrollBarRef} tabIndex={0}>
              <div
                className="table-hscroll-dock__sizer"
                style={{ width: tableSyncScrollWidth, height: 1 }}
                aria-hidden
              />
            </div>
          </div>
        </div>
      ) : null}

      {manageTopicsOpen ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => !formSaving && setManageTopicsOpen(false)}
        >
          <div
            className="modal"
            role="dialog"
            aria-labelledby="manage-topics-title"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal__head">
              <h2 id="manage-topics-title" className="modal__title">
                Topics &amp; search queries
              </h2>
              <button
                type="button"
                className="modal__close"
                onClick={() => !formSaving && setManageTopicsOpen(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <p className="modal__hint">
              Topic key: <code>a–z</code>, <code>0–9</code>, underscore. One YouTube search phrase per line.
            </p>
            <label className="modal__field">
              <span>Topic key</span>
              <input
                type="text"
                value={formTopicSlug}
                onChange={(e) => setFormTopicSlug(e.target.value)}
                placeholder="e.g. trail_running_gear"
                disabled={formSaving}
                readOnly={formSlugReadOnly}
                autoComplete="off"
              />
            </label>
            <label className="modal__field">
              <span>YouTube search queries (one per line)</span>
              <textarea
                className="modal__textarea"
                value={formQueriesText}
                onChange={(e) => setFormQueriesText(e.target.value)}
                rows={10}
                placeholder="best trail running shoes review&#10;ultra marathon gear 2024"
                disabled={formSaving}
              />
            </label>
            {formError ? <p className="err modal__err">{formError}</p> : null}
            <div className="modal__existing" aria-label="Existing topics">
              <span className="modal__existing-label">Quick edit</span>
              <ul className="modal__topic-chips">
                {topicRows.map((t) => (
                  <li key={t.topic}>
                    <button
                      type="button"
                      className="chip-btn"
                      onClick={() => openEditTopicForm(t.topic)}
                      disabled={formSaving}
                    >
                      {topicLabel(t.topic)}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div className="modal__actions">
              <button type="button" className="btn btn-ghost" onClick={openNewTopicForm} disabled={formSaving}>
                New topic
              </button>
              {formSlugReadOnly && formTopicSlug.trim() ? (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => void deleteTopic(formTopicSlug.trim())}
                  disabled={formSaving}
                >
                  Delete topic
                </button>
              ) : null}
              <button type="button" className="btn btn-primary" onClick={() => void saveTopicForm()} disabled={formSaving}>
                {formSaving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <footer className="app-footer">
        Data from YouTube Data API v3 · hunter
      </footer>
    </div>
  );
}
