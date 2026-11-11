import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, apiBlob, setToken as saveToken, token as savedToken } from "./api";

// ---------- shared bits ----------
function useTheme() {
  const [theme, setTheme] = useState(localStorage.getItem("reglens_theme") || "light");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("reglens_theme", theme);
  }, [theme]);
  return { theme, toggle: () => setTheme(theme === "light" ? "dark" : "light") };
}

function Modal({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ textAlign: "right" }}><button className="btn" onClick={onClose}>Close ✕</button></div>
        {children}
      </div>
    </div>
  );
}

function Err({ msg }: { msg: string }) {
  return msg ? <p style={{ color: "var(--red)" }}>{msg}</p> : null;
}

// ---------- Landing ----------
const FEATURES = [
  ["Clause-aware chunking", "Documents are split by clause and section — never by fixed token windows — so every citation points at a whole clause."],
  ["Hybrid GraphRAG", "BM25 + vector search + graph traversal (AMENDS, SUPERSEDES, REFERENCES), merged and re-ranked, with a visible retrieval trace."],
  ["Citation-grounded answers", "Every claim maps to a clause with document, version, page and exact excerpt. Uncited claims are blocked, not shown."],
  ["Honest abstention", "If the evidence is not in your documents, RegLens says so and shows what it searched — instead of inventing a clause."],
  ["Conflict candidates", "Incompatible obligations across contracts are surfaced side by side for human confirmation — never as legal verdicts."],
  ["Obligation register", "Every obligation, date and penalty, searchable and filterable by party, type and due date, exportable to CSV."],
  ["Knowledge graph", "Documents, clauses, parties, obligations and regulations linked — zoom, pan, explore, open the source clause."],
  ["Evidence packs & audit", "Export any answer as a PDF with question, citations, versions and audit reference. Every question is logged."],
];
const FAQS = [
  ["Does RegLens give legal advice?", "No. RegLens retrieves and summarises evidence for a qualified reviewer. It does not advise, sign, file or approve compliance."],
  ["What happens when the answer is not in my documents?", "RegLens abstains and shows what it searched, so you can add the right document or narrow the question. Abstention is a scored, correct behaviour."],
  ["How is access control enforced?", "During retrieval: clauses from collections you cannot access are filtered out before ranking and generation, so they can never be cited or leaked."],
  ["What document types are supported?", "PDF, DOCX and TXT in v1. Scanned or low-quality PDFs are flagged with a parse-quality score, not silently trusted."],
  ["Is my data used to train models?", "No. Documents are stored in your database; generation (optional, Groq) receives only retrieved clauses you can access."],
];

function Landing({ onStart, onLogin }: { onStart: () => void; onLogin: () => void }) {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  return (
    <div>
      <header className="landing-nav"><div className="landing-nav-in">
        <div className="logo">Reg<span>Lens</span></div>
        <nav className="nav-links">
          <a href="#features">Product</a><a href="#how">How it works</a><a href="#industries">Industries</a>
          <a href="#security">Security</a><a href="#faq">FAQ</a>
        </nav>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button className="btn" onClick={onLogin}>Login</button>
          <button className="btn btn-primary" onClick={onStart}>Get Started</button>
        </div>
      </div></header>

      <section className="hero">
        <span className="badge">AI-Powered Contract Intelligence</span>
        <h1 style={{ marginTop: 14 }}>Understand Every Clause.<br />Trust Every Answer.</h1>
        <p className="muted" style={{ fontSize: 18, maxWidth: 640 }}>
          RegLens reads contracts, policies and regulatory circulars as a structured knowledge
          graph — and answers only with clause-level citations a lawyer or auditor can verify.
          If the evidence is not there, it says so.
        </p>
        <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
          <button className="btn btn-primary" onClick={onStart}>Start Free</button>
          <button className="btn" onClick={onStart}>Explore Platform</button>
        </div>
        <div className="card" style={{ marginTop: 36 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong>Product preview — AI Ask</strong>
            <span className="badge">Interactive in the app</span>
          </div>
          <p className="muted small">“What is the current termination penalty if Acme Corp ends the Master Services Agreement?”</p>
          <div className="citation" onClick={onStart}>
            <strong>[C1] Amendment No. 1, Clause 2 — New Termination Clause (p. 1)</strong>
            <blockquote>“…Acme Corp shall pay Nimbus Technologies a termination penalty of ₹2,50,000. The termination penalty of ₹2,50,000 replaces the earlier penalty of ₹5,00,000…”</blockquote>
          </div>
          <p className="small muted">Every claim opens the exact clause in its document. Click any citation to verify it.</p>
        </div>
      </section>

      <section className="section"><h2>The problem</h2>
        <p className="muted">Finding the right clause takes hours. Connecting it to its amendment, its dates and its counterparty takes longer. And a normal RAG chatbot answers in seconds — sometimes inventing the clause. An unsupported answer is worse than no answer, because it looks finished.</p>
        <p><strong>The RegLens answer:</strong> parse by clause, extract parties, dates, obligations and penalties into a graph, retrieve with hybrid search, and refuse to show a claim without a citation.</p>
      </section>

      <section className="section" id="features"><h2>Core features</h2>
        <div className="grid grid-2" style={{ marginTop: 16 }}>
          {FEATURES.map(([t, d]) => (<div className="card" key={t}><h3>{t}</h3><p className="muted">{d}</p></div>))}
        </div>
      </section>

      <section className="section" id="how"><h2>How RegLens works</h2>
        <ol style={{ fontSize: 16, lineHeight: 2 }}>
          <li><strong>Upload</strong> PDF or DOCX contracts, policies and circulars.</li>
          <li><strong>Structure</strong> — clause chunking, extraction, knowledge-graph build, hybrid indexing.</li>
          <li><strong>Ask</strong> — hybrid retrieval with a trace, citation-grounded generation, faithfulness check.</li>
          <li><strong>Verify</strong> — click any citation to the exact clause; export an evidence pack for the file.</li>
        </ol>
      </section>

      <section className="section" id="industries"><h2>Industries</h2>
        <div className="grid grid-4">
          {["Banking", "Insurance", "Fintech", "Legal & Compliance"].map((i) => (
            <div className="card" key={i}><strong>{i}</strong><p className="muted small">Vendor contracts, policies and circulars — answered with evidence.</p></div>
          ))}
        </div>
      </section>

      <section className="section" id="security"><h2>Security &amp; trust</h2>
        <p className="muted">JWT authentication with salted password hashing. Role-based access (Admin / Reviewer / Viewer) plus collection-level permissions enforced inside retrieval — not just in the UI. PII redaction in traces, rate limiting, full audit trail, and secrets only in environment variables. Document text is treated as data, never as instructions.</p>
        <h3 style={{ marginTop: 24 }}>Technical capabilities</h3>
        <p className="muted">FastAPI + Pydantic backend, PostgreSQL (+pgvector path) / SQLite local dev, Redis + worker in Compose, BM25 + TF-vector + graph retrieval with re-ranking, faithfulness gate, RAGAS-style evaluation on a 47-case golden set with a four-way ablation. See the README for the real measured numbers.</p>
      </section>

      <section className="section" id="faq"><h2>FAQ</h2>
        {FAQS.map(([q, a], i) => (
          <div className="card" key={q} style={{ marginBottom: 10 }}>
            <button className="btn" style={{ border: "none", padding: 0, fontWeight: 700 }} onClick={() => setOpenFaq(openFaq === i ? null : i)}>{q}</button>
            {openFaq === i && <p className="muted" style={{ marginTop: 8 }}>{a}</p>}
          </div>
        ))}
      </section>

      <footer><div style={{ maxWidth: 1120, margin: "0 auto" }}>
        <strong style={{ color: "var(--ink)" }}>RegLens</strong> — Grounded GraphRAG for Contracts &amp; Compliance.<br />
        <span className="small">RegLens provides evidence, not legal advice. Demo data in the app is synthetic and labelled as such.</span>
      </div></footer>
    </div>
  );
}

// ---------- Auth ----------
function Auth({ onAuthed, goLanding }: { onAuthed: (u: any) => void; goLanding: () => void }) {
  const [mode, setMode] = useState<"login" | "register" | "forgot" | "reset">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(""); setMsg(""); setBusy(true);
    try {
      if (mode === "login") {
        const r = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
        saveToken(r.token); onAuthed(r.user);
      } else if (mode === "register") {
        const r = await api("/api/auth/register", { method: "POST", body: JSON.stringify({ name, email, password }) });
        saveToken(r.token); onAuthed(r.user);
        setMsg("Account created. The first account on a fresh system becomes Admin.");
      } else if (mode === "forgot") {
        const r = await api("/api/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
        if (r.dev_reset_token) { setResetToken(r.dev_reset_token); setMode("reset"); }
        setMsg("If the email exists, a reset token was issued (dev-only: shown below, since no email provider is configured in v1).");
      } else {
        await api("/api/auth/reset-password", { method: "POST", body: JSON.stringify({ token: resetToken, new_password: password }) });
        setMsg("Password reset. Please sign in."); setMode("login");
      }
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div style={{ maxWidth: 440, margin: "60px auto", padding: 20 }}>
      <div className="logo" style={{ fontSize: 26 }}>Reg<span>Lens</span></div>
      <h1 style={{ marginTop: 16 }}>{mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Forgot password" : "Reset password"}</h1>
      <p className="muted small">The first account registered on a fresh system becomes Admin.</p>
      <form onSubmit={submit} className="grid" style={{ marginTop: 16 }}>
        {mode === "register" && <input placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} required />}
        <input placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        {mode === "forgot" ? null : <input placeholder={mode === "reset" ? "New password (min 8 chars)" : "Password (min 8 chars)"} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />}
        {mode === "reset" && <input placeholder="Reset token" value={resetToken} onChange={(e) => setResetToken(e.target.value)} required />}
        <button className="btn btn-primary" disabled={busy}>{busy ? "Working…" : mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Send reset token" : "Reset password"}</button>
      </form>
      <Err msg={err} />
      {msg && <p style={{ color: "var(--green)" }}>{msg}</p>}
      {resetToken && mode === "reset" && <p className="small"><strong>Dev-only reset token:</strong> <code>{resetToken}</code></p>}
      <div style={{ display: "flex", gap: 14, marginTop: 16, fontSize: 14 }}>
        {mode !== "login" && <a href="#" onClick={(e) => { e.preventDefault(); setMode("login"); }}>Sign in</a>}
        {mode !== "register" && <a href="#" onClick={(e) => { e.preventDefault(); setMode("register"); }}>Create account</a>}
        {mode !== "forgot" && mode !== "reset" && <a href="#" onClick={(e) => { e.preventDefault(); setMode("forgot"); }}>Forgot password?</a>}
        <a href="#" onClick={(e) => { e.preventDefault(); goLanding(); }}>← Back to site</a>
      </div>
    </div>
  );
}

// ---------- App shell ----------
const NAV = [
  ["overview", "Overview"], ["library", "Document Library"], ["upload", "Upload Documents"],
  ["ask", "AI Ask"], ["compare", "Compare Documents"], ["conflicts", "Conflict Detection"],
  ["obligations", "Obligation Register"], ["graph", "Knowledge Graph"], ["history", "Answer History"],
  ["evidence", "Evidence Packs"], ["admin", "Evaluation & Admin"], ["settings", "Settings"],
] as const;
type View = (typeof NAV)[number][0];

function useApi<T>(path: string | null, deps: any[] = []): { data: T | null; err: string; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    api(path).then((d) => live && setData(d)).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [path, tick, ...deps]);
  return { data, err, reload: () => setTick((t) => t + 1) };
}

function ClauseModal({ docId, clauseId, onClose }: { docId: string; clauseId?: string; onClose: () => void }) {
  const { data: clauseData } = useApi<any>(!docId && clauseId ? `/api/clauses/${clauseId}` : null);
  const resolvedDocId = docId || clauseData?.document_id || "";
  const { data } = useApi<any>(resolvedDocId ? `/api/documents/${resolvedDocId}` : null);
  if (!data) return <Modal onClose={onClose}><p>Loading document…</p></Modal>;
  const clauses = data.clauses || [];
  return (
    <Modal onClose={onClose}>
      <h2>{data.title} {data.is_demo && <span className="badge badge-demo">DEMO / SYNTHETIC</span>}</h2>
      <p className="muted small">Version {data.current_version} · Status: {data.status} · Parse quality: {Math.round((data.parse_quality || 1) * 100)}%</p>
      {clauses.map((c: any) => (
        <div key={c.id} id={`clause-${c.id}`} style={c.id === clauseId ? { background: "var(--blue-soft)", borderRadius: 8, padding: 10 } : { padding: 10 }}>
          <strong>Clause {c.clause_no} — {c.heading}</strong> <span className="muted small">(p. {c.page_ref})</span>
          {!c.is_current && <span className="badge badge-warn" style={{ marginLeft: 6 }}>SUPERSEDED</span>}
          <p style={{ margin: "6px 0 0" }}>{c.text}</p>
        </div>
      ))}
    </Modal>
  );
}

function Overview({ user }: { user: any }) {
  const { data, err, reload } = useApi<any>("/api/overview");
  const { data: recent } = useApi<any[]>("/api/history");
  const [seedMsg, setSeedMsg] = useState("");
  async function seed() {
    try { const r = await api("/api/admin/seed", { method: "POST" }); setSeedMsg(`Demo data loaded: ${r.created} new documents, ${r.documents} total, ${r.clauses} clauses.`); reload(); }
    catch (e: any) { setSeedMsg(e.message); }
  }
  if (!data) return <p>Loading overview…</p>;
  return (
    <div>
      <Err msg={err} />
      <div className="grid grid-4">
        {[["Total Documents", data.total_documents], ["Indexed Clauses", data.indexed_clauses],
          ["Active Collections", data.active_collections], ["Pending Ingestion", data.pending_ingestion],
          ["Detected Conflicts", data.detected_conflicts], ["Upcoming Obligations", data.upcoming_obligations],
          ["Your Questions", data.recent_questions], ["AI cost (you, $)", data.total_cost_usd]].map(([l, v]) => (
          <div className="card" key={l as string}><div className="muted small">{l}</div><div className="stat-num">{v}</div></div>
        ))}
      </div>
      <p className="small muted" style={{ marginTop: 10 }}>{data.demo_data_note}</p>
      {data.failed_ingestion > 0 && <p><span className="badge badge-bad">{data.failed_ingestion} failed ingestion(s)</span> — see Evaluation &amp; Admin → Ingestion health.</p>}
      {user.role === "admin" && (
        <div className="card" style={{ marginTop: 16 }}>
          <strong>Demo data</strong>
          <p className="muted small">Load 5 synthetic vendor contracts + 1 RBI-style circular + 1 restricted board document (labelled DEMO / SYNTHETIC). The demo journey: ask about termination penalties, click citations, ask an unanswerable question, check conflicts.</p>
          <button className="btn btn-primary" onClick={seed}>Load demo data</button>
          {seedMsg && <p className="small">{seedMsg}</p>}
        </div>
      )}
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Recent AI queries</h3>
        {(recent || []).slice(0, 5).map((q: any) => (
          <p key={q.id} className="small" style={{ margin: "8px 0" }}>
            {q.question} — <span className="muted">{q.status}{q.status === "stale" ? " (source document updated)" : ""} · confidence {q.confidence} · {q.mode}</span>
          </p>
        ))}
        {(!recent || recent.length === 0) && <p className="muted small">No questions yet — open AI Ask.</p>}
      </div>
    </div>
  );
}

function Library() {
  const { data: docs, reload } = useApi<any[]>("/api/documents");
  const { data: cols } = useApi<any[]>("/api/collections");
  const [q, setQ] = useState("");
  const [coll, setColl] = useState("");
  const [status, setStatus] = useState("");
  const [openDoc, setOpenDoc] = useState<string | null>(null);
  const [reproc, setReproc] = useState("");
  const filtered = (docs || []).filter((d: any) =>
    (!q || d.title.toLowerCase().includes(q.toLowerCase())) &&
    (!coll || d.collection_id === coll) && (!status || d.status === status));
  async function reprocess(id: string) {
    try { await api(`/api/documents/${id}/reprocess`, { method: "POST" }); setReproc("Reprocessed — status updated."); reload(); }
    catch (e: any) { setReproc(e.message); }
  }
  return (
    <div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <input placeholder="Search documents…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 260 }} />
        <select value={coll} onChange={(e) => setColl(e.target.value)} style={{ maxWidth: 240 }}>
          <option value="">All collections</option>
          {(cols || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ maxWidth: 180 }}>
          <option value="">All statuses</option>
          {["ready", "processing", "failed", "uploaded"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      {reproc && <p className="small">{reproc}</p>}
      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table><thead><tr><th>Document</th><th>Collection</th><th>Type</th><th>Status</th><th>Clauses</th><th>Quality</th><th></th></tr></thead>
          <tbody>
            {filtered.map((d: any) => (
              <tr key={d.id}>
                <td>{d.title} {d.is_demo && <span className="badge badge-demo">DEMO</span>}</td>
                <td>{d.collection_name}</td><td>{d.doc_type}</td>
                <td>{d.status === "ready" ? <span className="badge badge-ok">Ready</span> : d.status === "failed" ? <span className="badge badge-bad">Failed</span> : <span className="badge badge-warn">{d.status}</span>}{d.error && <div className="small muted">{d.error}</div>}</td>
                <td>{d.clauses}</td><td>{Math.round((d.parse_quality || 1) * 100)}%</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="btn" onClick={() => setOpenDoc(d.id)}>Open</button>{" "}
                  {d.status === "failed" && <button className="btn" onClick={() => reprocess(d.id)}>Retry</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="muted" style={{ padding: 16 }}>No documents match. Upload some, or load demo data from Overview (Admin).</p>}
      </div>
      {openDoc && <DocDetail docId={openDoc} onClose={() => setOpenDoc(null)} onReprocess={reprocess} />}
    </div>
  );
}

function DocDetail({ docId, onClose, onReprocess }: { docId: string; onClose: () => void; onReprocess: (id: string) => void }) {
  const { data } = useApi<any>(`/api/documents/${docId}`);
  const [tab, setTab] = useState("clauses");
  if (!data) return <Modal onClose={onClose}><p>Loading…</p></Modal>;
  return (
    <Modal onClose={onClose}>
      <h2>{data.title} {data.is_demo && <span className="badge badge-demo">DEMO / SYNTHETIC</span>}</h2>
      <dl className="kv">
        <dt>Collection</dt><dd>{data.collection_name}</dd>
        <dt>Status</dt><dd>{data.status} · parse quality {Math.round((data.parse_quality || 1) * 100)}% {data.parse_notes}</dd>
        <dt>Version</dt><dd>{data.current_version} ({data.versions?.length || 1} version(s) stored)</dd>
        <dt>Graph edges</dt><dd>{data.graph_edges}</dd>
      </dl>
      <div className="tabs" style={{ marginTop: 14 }}>
        {(["clauses", "obligations", "versions"] as const).map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>
        ))}
        <button onClick={() => onReprocess(docId)}>Reprocess</button>
      </div>
      {tab === "clauses" && (data.clauses || []).map((c: any) => (
        <div key={c.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
          <strong>Clause {c.clause_no} — {c.heading}</strong> <span className="muted small">(p. {c.page_ref})</span>
          {!c.is_current && <span className="badge badge-warn" style={{ marginLeft: 6 }}>SUPERSEDED</span>}
          <p style={{ margin: "4px 0 0" }}>{c.text}</p>
        </div>
      ))}
      {tab === "obligations" && ((data.obligations || []).length === 0 ? <p className="muted">No obligations extracted from this document.</p> :
        <table><thead><tr><th>Party</th><th>Obligation</th><th>Type</th><th>Penalty</th><th>Due</th></tr></thead>
          <tbody>{data.obligations.map((o: any) => (
            <tr key={o.id}><td>{o.party}</td><td>{o.obligation}</td><td>{o.type}</td><td>{o.penalty}</td><td>{o.due_date || "—"}</td></tr>
          ))}</tbody></table>)}
      {tab === "versions" && (data.versions || []).map((v: any) => (
        <p key={v.version_no} className="small">Version {v.version_no} — {v.chars} characters — {v.created_at}</p>
      ))}
    </Modal>
  );
}

function Upload() {
  const { data: cols, reload: reloadCols } = useApi<any[]>("/api/collections");
  const [coll, setColl] = useState("");
  const [drag, setDrag] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [newColl, setNewColl] = useState("");
  useEffect(() => { if (cols && cols.length && !coll) setColl(cols[0].id); }, [cols]);
  async function uploadFiles(files: FileList | File[]) {
    if (!coll) { setResults([{ error: "Pick a collection first." }]); return; }
    setBusy(true);
    const out: any[] = [];
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append("file", f); fd.append("collection_id", coll);
      try {
        const res = await fetch(`${(await import("./api")).API_BASE}/api/documents`, {
          method: "POST", headers: { Authorization: `Bearer ${savedToken()}` }, body: fd,
        });
        const body = await res.json();
        if (res.status === 409) {
          out.push({ file: f.name, duplicate: body, error: body.detail });
        } else if (!res.ok) {
          out.push({ file: f.name, error: body.detail || `Failed (${res.status})` });
        } else {
          out.push({ file: f.name, ok: true, clauses: body.ingestion?.clauses, status: body.status });
        }
      } catch (e: any) { out.push({ file: f.name, error: e.message }); }
    }
    setResults(out); setBusy(false);
  }
  async function uploadAsVersion(file: File, docId: string) {
    const fd = new FormData();
    fd.append("file", file); fd.append("collection_id", coll); fd.append("as_version_of", docId);
    const res = await fetch(`${(await import("./api")).API_BASE}/api/documents`, {
      method: "POST", headers: { Authorization: `Bearer ${savedToken()}` }, body: fd,
    });
    const body = await res.json();
    setResults([{ file: file.name, ok: res.ok, status: body.status, version: body.current_version, error: body.detail }]);
  }
  async function createCollection() {
    if (!newColl.trim()) return;
    await api("/api/collections", { method: "POST", body: JSON.stringify({ name: newColl.trim() }) });
    setNewColl(""); reloadCols();
  }
  return (
    <div>
      <div className="card" style={{ marginBottom: 14 }}>
        <label className="small muted">Collection</label>
        <select value={coll} onChange={(e) => setColl(e.target.value)}>
          {(cols || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <input placeholder="New collection name" value={newColl} onChange={(e) => setNewColl(e.target.value)} />
          <button className="btn" onClick={createCollection}>Create collection</button>
        </div>
      </div>
      <div className={`dropzone${drag ? " drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); uploadFiles(e.dataTransfer.files); }}>
        <p><strong>Drag &amp; drop PDF, DOCX or TXT files here</strong></p>
        <p className="small">Multiple files supported · max 25 MB each · SHA-256 duplicate detection with versioning</p>
        <input type="file" multiple accept=".pdf,.docx,.txt,.md" onChange={(e) => e.target.files && uploadFiles(e.target.files)} />
      </div>
      {busy && <p>Uploading &amp; ingesting…</p>}
      {results.map((r, i) => (
        <div className="card" key={i} style={{ marginTop: 10 }}>
          <strong>{r.file}</strong>{" "}
          {r.ok ? <span className="badge badge-ok">Ready · {r.clauses ?? "?"} clauses{r.version ? ` · v${r.version}` : ""}</span>
            : <span className="badge badge-bad">Failed</span>}
          {r.error && <p className="small">{r.error}</p>}
          {r.duplicate && (
            <div style={{ marginTop: 8 }}>
              <p className="small">Matches existing document “{r.duplicate.duplicate_of.title}” (v{r.duplicate.duplicate_of.version}).</p>
              <button className="btn" onClick={async () => {
                const input = document.querySelector('input[type="file"]') as HTMLInputElement;
                const f = input?.files?.[0];
                if (f) await uploadAsVersion(f, r.duplicate.duplicate_of.id);
              }}>Upload as new version instead</button>
              <span className="small muted"> — re-select the same file first if needed; previous answers citing it will be flagged stale.</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

const SUGGESTED = [
  "What is the current termination penalty if Acme Corp ends the Master Services Agreement for convenience?",
  "What are the termination penalties across all vendor contracts?",
  "What audit rights does the RBI circular require for IT service providers?",
  "What is the late payment penalty under the Supply Agreement?",
  "What is the arbitration venue for disputes under these contracts?",
];

function Ask() {
  const { data: cols } = useApi<any[]>("/api/collections");
  const [question, setQuestion] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [answer, setAnswer] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [clauseOpen, setClauseOpen] = useState<any | null>(null);
  const [showTrace, setShowTrace] = useState(false);

  async function ask(q?: string) {
    const text = (q ?? question).trim();
    if (text.length < 3) return;
    setBusy(true); setErr(""); setAnswer(null);
    try {
      const r = await api("/api/ask", { method: "POST", body: JSON.stringify({ question: text, collection_ids: selected.length ? selected : null }) });
      setAnswer(r);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div>
      <div className="card">
        <label className="small muted">Collections to search (empty = all you can access)</label>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", margin: "8px 0" }}>
          {(cols || []).map((c: any) => (
            <label key={c.id} className="small" style={{ display: "flex", gap: 5, alignItems: "center" }}>
              <input type="checkbox" style={{ width: "auto" }} checked={selected.includes(c.id)}
                onChange={(e) => setSelected(e.target.checked ? [...selected, c.id] : selected.filter((x) => x !== c.id))} />
              {c.name}
            </label>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="Ask a question about your contracts…" value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()} />
          <button className="btn btn-primary" onClick={() => ask()} disabled={busy}>{busy ? "Searching…" : "Ask"}</button>
        </div>
        <p className="small muted" style={{ marginTop: 10 }}>Suggested:</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {SUGGESTED.map((s) => <button key={s} className="btn small" onClick={() => { setQuestion(s); ask(s); }}>{s.slice(0, 60)}…</button>)}
        </div>
      </div>
      <Err msg={err} />
      {busy && <p>Retrieving clauses (BM25 + vector + graph)…</p>}
      {answer && (
        <div className="card" style={{ marginTop: 14 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span className={`badge ${answer.status === "abstained" ? "badge-warn" : answer.status === "answered" ? "badge-ok" : "badge-demo"}`}>{answer.status.toUpperCase()}</span>
            <span className="small muted">Mode: {answer.mode} · Confidence: {answer.confidence}
              {answer.model ? ` · ${answer.model}` : ""} · {answer.latency_ms} ms
              {answer.tokens ? ` · ${answer.tokens} tokens · $${answer.cost_usd}` : " · 0 tokens (extractive)"}</span>
          </div>
          {answer.status === "abstained" ? (
            <div>
              <p style={{ marginTop: 12 }}><strong>{answer.answer}</strong></p>
              <p className="muted small">What was searched: {answer.searched?.clauses_considered ?? 0} clauses considered
                across collections you can access. {answer.searched?.note || ""}</p>
              {(answer.searched?.retrieved || []).length > 0 && (
                <p className="small">Closest clauses found (none supported an answer):</p>
              )}
              {(answer.searched?.retrieved || []).map((r: any) => (
                <p key={r.clause_id} className="small muted">• {r.document_title}, Clause {r.clause_no}</p>
              ))}
            </div>
          ) : (
            <div>
              <p style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>{answer.answer}</p>
              {answer.confidence_basis && (
                <p className="small muted">Confidence basis: {answer.confidence_basis.supporting_clauses} supporting clause(s) across {answer.confidence_basis.documents_cited} document(s); faithfulness {answer.confidence_basis.faithfulness}. {answer.confidence_basis.note}</p>
              )}
              <h3 style={{ marginTop: 16 }}>Citations — click to open the clause in context</h3>
              {answer.citations.map((c: any) => (
                <div key={c.clause_id} className="citation" onClick={() => setClauseOpen(c)}>
                  <strong>[C{c.citation_no}] {c.document_title} (v{c.version}), Clause {c.clause_no} — {c.heading} (p. {c.page_ref})</strong>
                  <span className="small muted" style={{ marginLeft: 8 }}>support {c.support} · score {c.score}</span>
                  <blockquote>{c.text}</blockquote>
                </div>
              ))}
              <button className="btn" onClick={() => setShowTrace(!showTrace)}>{showTrace ? "Hide" : "Show"} retrieval trace</button>
              {showTrace && answer.retrieval_trace && (
                <table style={{ marginTop: 10 }}><thead><tr><th>Clause</th><th>Score</th><th>BM25</th><th>Vector</th><th>Graph</th><th>Overlap</th></tr></thead>
                  <tbody>{answer.retrieval_trace.map((t: any) => {
                    const c = answer.citations.find((x: any) => x.clause_id === t.clause_id);
                    return <tr key={t.clause_id}><td>{c ? `${c.document_title} §${c.clause_no}` : t.clause_id.slice(0, 8)}</td><td>{t.score}</td><td>{t.trace.bm25}</td><td>{t.trace.vector}</td><td>{t.trace.graph}</td><td>{t.trace.overlap}</td></tr>;
                  })}</tbody></table>
              )}
              <div style={{ marginTop: 12 }}>
                <button className="btn" onClick={async () => {
                  const blob = await apiBlob("/api/evidence-pack", { method: "POST", body: JSON.stringify({ question_id: answer.question_id }) });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a"); a.href = url; a.download = `evidence-pack-${answer.question_id.slice(0, 8)}.pdf`; a.click();
                  URL.revokeObjectURL(url);
                }}>Download evidence pack (PDF)</button>
              </div>
            </div>
          )}
        </div>
      )}
      {clauseOpen && <ClauseModal docId={clauseOpen.document_id} clauseId={clauseOpen.clause_id} onClose={() => setClauseOpen(null)} />}
    </div>
  );
}

function Compare() {
  const { data: docs } = useApi<any[]>("/api/documents");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [result, setResult] = useState<any | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (docs && docs.length >= 2 && !a) { setA(docs[0].id); setB(docs[1].id); } }, [docs]);
  async function run() {
    if (!a || !b || a === b) { setErr("Pick two different documents."); return; }
    setBusy(true); setErr("");
    try { setResult(await api("/api/compare", { method: "POST", body: JSON.stringify({ doc_a_id: a, doc_b_id: b }) })); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div>
      <div className="card" style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "end" }}>
        <div style={{ flex: 1, minWidth: 220 }}><label className="small muted">Document A</label>
          <select value={a} onChange={(e) => setA(e.target.value)}>{(docs || []).map((d: any) => <option key={d.id} value={d.id}>{d.title}</option>)}</select></div>
        <div style={{ flex: 1, minWidth: 220 }}><label className="small muted">Document B</label>
          <select value={b} onChange={(e) => setB(e.target.value)}>{(docs || []).map((d: any) => <option key={d.id} value={d.id}>{d.title}</option>)}</select></div>
        <button className="btn btn-primary" onClick={run} disabled={busy}>{busy ? "Comparing…" : "Compare"}</button>
      </div>
      <Err msg={err} />
      {result && (
        <div style={{ marginTop: 14 }}>
          <p className="muted small">{result.note}</p>
          {result.conflict_candidates.length > 0 && (
            <div className="card" style={{ marginBottom: 14, borderColor: "var(--amber)" }}>
              <h3>⚠ Conflict candidates ({result.conflict_candidates.length})</h3>
              {result.conflict_candidates.map((c: any) => (
                <p key={c.id} className="small"><strong>{c.topic}</strong> — {c.party}: {c.explanation} <span className="badge badge-warn">{c.status}</span></p>
              ))}
            </div>
          )}
          {result.pairs.map((p: any, i: number) => (
            <div key={i} className="card" style={{ marginBottom: 12 }}>
              <p><strong>Similarity {p.similarity}</strong> — Clause {p.clause_a.clause_no} ({p.clause_a.heading}) vs Clause {p.clause_b.clause_no} ({p.clause_b.heading})</p>
              <div className="grid grid-2">
                <div><strong className="small">{result.doc_a}</strong><p className="small">{p.clause_a.text}</p></div>
                <div><strong className="small">{result.doc_b}</strong><p className="small">{p.clause_b.text}</p></div>
              </div>
              <p className="small muted">Only in A: {p.diff.only_in_a.slice(0, 10).join(", ") || "—"} · Only in B: {p.diff.only_in_b.slice(0, 10).join(", ") || "—"}</p>
            </div>
          ))}
          {result.pairs.length === 0 && <p className="muted">No similar clause pairs found above the similarity threshold.</p>}
        </div>
      )}
    </div>
  );
}

function Conflicts() {
  const { data, reload } = useApi<any[]>("/api/conflicts");
  const [msg, setMsg] = useState("");
  async function act(id: string, action: string) {
    try { await api(`/api/conflicts/${id}/${action}`, { method: "POST" }); setMsg(`Conflict ${action === "confirm" ? "confirmed" : "dismissed"}.`); reload(); }
    catch (e: any) { setMsg(e.message); }
  }
  return (
    <div>
      <p className="muted">Candidates are surfaced for human confirmation. RegLens does not decide which clause governs.</p>
      {msg && <p className="small">{msg}</p>}
      {(data || []).length === 0 && <p className="muted">No conflict candidates yet. Seed demo data (Overview → Admin) to see the Acme termination-penalty candidate.</p>}
      {(data || []).map((c: any) => (
        <div key={c.id} className="card" style={{ marginBottom: 12 }}>
          <p><strong>{c.topic}</strong> — {c.party} <span className="badge badge-warn">{c.status}</span></p>
          <p className="small">{c.explanation}</p>
          <div className="grid grid-2">
            <div><strong className="small">{c.clause_a.document}, Clause {c.clause_a.clause_no}</strong><p className="small">{c.clause_a.text}</p></div>
            <div><strong className="small">{c.clause_b.document}, Clause {c.clause_b.clause_no}</strong><p className="small">{c.clause_b.text}</p></div>
          </div>
          {c.status === "candidate" && (
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn" onClick={() => act(c.id, "confirm")}>Confirm conflict</button>
              <button className="btn" onClick={() => act(c.id, "dismiss")}>Dismiss</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Obligations() {
  const [party, setParty] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [dueBefore, setDueBefore] = useState("");
  const [dueAfter, setDueAfter] = useState("");
  const query = useMemo(() => {
    const p = new URLSearchParams();
    if (party) p.set("party", party);
    if (type) p.set("obligation_type", type);
    if (status) p.set("status", status);
    if (dueBefore) p.set("due_before", dueBefore);
    if (dueAfter) p.set("due_after", dueAfter);
    return p.toString();
  }, [party, type, status, dueBefore, dueAfter]);
  const { data } = useApi<any[]>(`/api/obligations?${query}`, [query]);
  const [openClause, setOpenClause] = useState<any | null>(null);
  return (
    <div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <input placeholder="Filter by party" value={party} onChange={(e) => setParty(e.target.value)} style={{ maxWidth: 200 }} />
        <select value={type} onChange={(e) => setType(e.target.value)} style={{ maxWidth: 180 }}>
          <option value="">All types</option>
          {["payment", "termination", "delivery", "notice", "compliance", "other"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ maxWidth: 160 }}>
          <option value="">All statuses</option>
          {["active", "fulfilled", "overdue", "superseded"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label className="small muted">Due after <input type="date" value={dueAfter} onChange={(e) => setDueAfter(e.target.value)} style={{ width: 150 }} /></label>
        <label className="small muted">Due before <input type="date" value={dueBefore} onChange={(e) => setDueBefore(e.target.value)} style={{ width: 150 }} /></label>
        <button className="btn" onClick={async () => {
          const blob = await apiBlob(`/api/obligations/export`);
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a"); a.href = url; a.download = "obligation-register.csv"; a.click();
          URL.revokeObjectURL(url);
        }}>Export CSV</button>
      </div>
      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table><thead><tr><th>Document</th><th>Party</th><th>Obligation</th><th>Type</th><th>Effective</th><th>Due</th><th>Penalty</th><th>Status</th><th>Clause</th></tr></thead>
          <tbody>{(data || []).map((o: any) => (
            <tr key={o.id}>
              <td>{o.document}</td><td>{o.party}</td><td>{o.obligation}</td><td>{o.type}</td>
              <td>{o.effective_date || "—"}</td><td>{o.due_date || "—"}</td><td>{o.penalty || "—"}</td>
              <td>{o.status}</td>
              <td><button className="btn small" onClick={() => setOpenClause(o)}>§{o.source_clause_no}</button></td>
            </tr>
          ))}</tbody>
        </table>
        {(data || []).length === 0 && <p className="muted" style={{ padding: 16 }}>No obligations match these filters.</p>}
      </div>
      {openClause && <ClauseModal docId={openClause.document_id} clauseId={openClause.clause_id} onClose={() => setOpenClause(null)} />}
    </div>
  );
}

function Graph() {
  const { data } = useApi<any>("/api/graph");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [sel, setSel] = useState<any | null>(null);
  const [openClause, setOpenClause] = useState<any | null>(null);
  const dragRef = useRef<{ x: number; y: number } | null>(null);
  const nodes = data?.nodes || [];
  const edges = data?.edges || [];
  const pos = useMemo(() => {
    const m: Record<string, { x: number; y: number }> = {};
    const byType: Record<string, any[]> = {};
    nodes.forEach((n: any) => { (byType[n.type] = byType[n.type] || []).push(n); });
    const types = Object.keys(byType);
    types.forEach((t, ti) => {
      byType[t].forEach((n: any, i: number) => {
        const angle = (i / Math.max(byType[t].length, 1)) * Math.PI * 2;
        const r = 90 + ti * 110;
        m[n.id] = { x: 400 + r * Math.cos(angle), y: 300 + r * Math.sin(angle) };
      });
    });
    return m;
  }, [nodes]);
  const colors: Record<string, string> = { Document: "#0b1f3a", Clause: "#2563eb", Party: "#15803d", Obligation: "#b45309", DateEvent: "#7c3aed", Regulation: "#be185d" };
  return (
    <div>
      <p className="muted small">Nodes: Document · Clause · Party · Obligation · DateEvent · Regulation. Edges: CONTAINS · BINDS · IMPOSES · AMENDS · SUPERSEDES · REFERENCES · CONFLICTS_WITH (candidates, not verdicts). Drag to pan, scroll or use buttons to zoom, click a node to explore.</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <button className="btn" onClick={() => setZoom((z) => Math.min(2.5, z + 0.2))}>Zoom +</button>
        <button className="btn" onClick={() => setZoom((z) => Math.max(0.4, z - 0.2))}>Zoom −</button>
        <button className="btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>Reset view</button>
        <span className="small muted">{nodes.length} nodes · {edges.length} edges</span>
      </div>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <svg width="100%" height="560" viewBox="0 0 800 600"
          onMouseDown={(e) => { dragRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }; }}
          onMouseMove={(e) => { if (dragRef.current) setPan({ x: e.clientX - dragRef.current.x, y: e.clientY - dragRef.current.y }); }}
          onMouseUp={() => { dragRef.current = null; }}
          onMouseLeave={() => { dragRef.current = null; }}
          onWheel={(e) => { e.preventDefault(); setZoom((z) => Math.min(2.5, Math.max(0.4, z - e.deltaY * 0.001))); }}>
          <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
            {edges.map((e: any) => {
              const a = pos[e.source], b = pos[e.target];
              if (!a || !b) return null;
              return <line key={e.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={e.rel === "CONFLICTS_WITH" ? "#b45309" : e.rel === "SUPERSEDES" ? "#b91c1c" : "#94a3b8"} strokeWidth={e.rel === "CONFLICTS_WITH" ? 2.5 : 1.2} strokeDasharray={e.rel === "SUPERSEDES" ? "5,4" : undefined} />;
            })}
            {nodes.map((n: any) => {
              const p = pos[n.id];
              if (!p) return null;
              return (
                <g key={n.id} transform={`translate(${p.x},${p.y})`} onClick={() => setSel(n)} style={{ cursor: "pointer" }}>
                  <circle r={n.type === "Document" ? 14 : 9} fill={colors[n.type] || "#64748b"} stroke={sel?.id === n.id ? "#000" : "#fff"} strokeWidth={2} />
                  <text y={22} textAnchor="middle" fontSize={11} fill="var(--ink)">{(n.label || "").slice(0, 26)}</text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      {sel && (
        <div className="card" style={{ marginTop: 12 }}>
          <strong>{sel.type}: {sel.label}</strong>
          <p className="small muted">Connected edges:</p>
          {edges.filter((e: any) => e.source === sel.id || e.target === sel.id).map((e: any) => (
            <p key={e.id} className="small">• {e.rel}: {(nodes.find((n: any) => n.id === (e.source === sel.id ? e.target : e.source)) || {}).label || "?"}</p>
          ))}
          {sel.type === "Clause" && <button className="btn" onClick={() => setOpenClause(sel)}>Open source clause</button>}
        </div>
      )}
      {openClause && <ClauseModal docId={""} clauseId={openClause.id} onClose={() => setOpenClause(null)} />}
    </div>
  );
}

function History() {
  const { data } = useApi<any[]>("/api/history");
  const [open, setOpen] = useState<any | null>(null);
  return (
    <div>
      {(data || []).length === 0 && <p className="muted">No questions yet — ask something in AI Ask.</p>}
      {(data || []).map((q: any) => (
        <div key={q.id} className="card" style={{ marginBottom: 12 }}>
          <p><strong>{q.question}</strong> <span className={`badge ${q.status === "stale" ? "badge-warn" : q.status === "abstained" ? "badge-warn" : "badge-ok"}`}>{q.status.toUpperCase()}</span>
            {q.status === "stale" && <span className="small muted"> — a cited document was updated after this answer</span>}</p>
          <p className="small muted">{q.created_at} · confidence {q.confidence} · {q.mode} · {q.tokens} tokens · ${q.cost_usd}</p>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={() => setOpen(q)}>View answer &amp; citations</button>
            {q.status !== "abstained" && <button className="btn" onClick={async () => {
              const blob = await apiBlob("/api/evidence-pack", { method: "POST", body: JSON.stringify({ question_id: q.id }) });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a"); a.href = url; a.download = `evidence-pack-${q.id.slice(0, 8)}.pdf`; a.click();
              URL.revokeObjectURL(url);
            }}>Evidence pack (PDF)</button>}
          </div>
        </div>
      ))}
      {open && (
        <Modal onClose={() => setOpen(null)}>
          <h2>Answer</h2>
          <p className="muted small">{open.question} — {open.status} · model {open.model || "extractive"} · prompt {open.prompt_version}</p>
          <p style={{ whiteSpace: "pre-wrap" }}>{open.answer}</p>
          <h3>Citations</h3>
          {(open.citations || []).map((c: any) => (
            <div key={c.clause_id} className="citation">
              <strong>[C{c.citation_no}] {c.document_title} (v{c.version}), Clause {c.clause_no} — {c.heading} (p. {c.page_ref})</strong>
              <blockquote>{c.text}</blockquote>
            </div>
          ))}
        </Modal>
      )}
    </div>
  );
}

function Evidence() {
  const { data } = useApi<any[]>("/api/history");
  const answered = (data || []).filter((q: any) => q.status !== "abstained");
  return (
    <div>
      <p className="muted">Evidence packs bundle the question, answer, cited clauses, document versions, timestamps and audit reference into a PDF a second reviewer can file without opening RegLens.</p>
      {answered.length === 0 && <p className="muted">No answered questions yet.</p>}
      {answered.map((q: any) => (
        <div key={q.id} className="card" style={{ marginBottom: 10, display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <div><strong>{q.question}</strong><p className="small muted" style={{ margin: 0 }}>{q.created_at} · {q.status} · {q.citations?.length || 0} citations</p></div>
          <button className="btn" onClick={async () => {
            const blob = await apiBlob("/api/evidence-pack", { method: "POST", body: JSON.stringify({ question_id: q.id }) });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a"); a.href = url; a.download = `evidence-pack-${q.id.slice(0, 8)}.pdf`; a.click();
            URL.revokeObjectURL(url);
          }}>Download PDF</button>
        </div>
      ))}
    </div>
  );
}

function Admin() {
  const [tab, setTab] = useState<"eval" | "users" | "health" | "audit">("eval");
  const { data: users, reload: reloadUsers } = useApi<any[]>("/api/admin/users");
  const { data: health } = useApi<any>("/api/admin/health");
  const { data: audit } = useApi<any[]>("/api/admin/audit?limit=50");
  const { data: latest, reload: reloadEval } = useApi<any>("/api/admin/evals/latest");
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState("");
  async function runEval() {
    setRunning(true); setErr("");
    try { await api("/api/admin/evals/run", { method: "POST" }); reloadEval(); }
    catch (e: any) { setErr(e.message); } finally { setRunning(false); }
  }
  async function setRole(uid: string, role: string) {
    await api(`/api/admin/users/${uid}/role`, { method: "PATCH", body: JSON.stringify({ role }) });
    reloadUsers();
  }
  const scores = latest?.run ? latest.scores : null;
  return (
    <div>
      <div className="tabs">
        {(["eval", "users", "health", "audit"] as const).map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t === "eval" ? "Evaluation & Analytics" : t === "users" ? "User Management" : t === "health" ? "Ingestion Health" : "Audit Logs"}</button>
        ))}
      </div>
      {tab === "eval" && (
        <div>
          <div className="card" style={{ marginBottom: 14 }}>
            <h3>Golden-set evaluation</h3>
            <p className="muted small">47 cases (39 answerable, 8 unanswerable) scored with the real retrieval + faithfulness code. Runs the four-way ablation and stores the result.</p>
            <button className="btn btn-primary" onClick={runEval} disabled={running}>{running ? "Running evaluation…" : "Run evaluation"}</button>
            <Err msg={err} />
            {latest?.run && <p className="small muted" style={{ marginTop: 8 }}>Latest run: {latest.created_at} · dataset {latest.dataset_version} · mode {latest.model} · prompt {latest.prompt_version}</p>}
          </div>
          {scores ? (
            <div className="card" style={{ padding: 0, overflow: "auto" }}>
              <table><thead><tr><th>Retrieval mode</th><th>Precision@5</th><th>Recall@5</th><th>MRR</th><th>Faithfulness</th><th>Answer relevancy</th><th>Correct abstention</th></tr></thead>
                <tbody>{Object.entries(scores.ablation || {}).map(([mode, s]: any) => (
                  <tr key={mode}><td><strong>{mode}</strong></td><td>{s["context_precision@5"]}</td><td>{s["context_recall@5"]}</td><td>{s.mrr}</td><td>{s.faithfulness}</td><td>{s.answer_relevancy}</td><td>{s.correct_abstention_rate}</td></tr>
                ))}</tbody></table>
              <p className="small muted" style={{ padding: 12 }}>{scores.note}</p>
              {scores.per_category_context_recall_hybrid_graph && (
                <p className="small" style={{ padding: "0 12px 12px" }}>Per-category recall (hybrid+graph): {Object.entries(scores.per_category_context_recall_hybrid_graph).map(([k, v]: any) => `${k} ${v}`).join(" · ")}</p>
              )}
            </div>
          ) : <p className="muted">No evaluation run yet — run one above.</p>}
        </div>
      )}
      {tab === "users" && (
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Verified</th><th></th></tr></thead>
            <tbody>{(users || []).map((u: any) => (
              <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.email_verified ? "Yes" : "No"}</td>
                <td><select value={u.role} onChange={(e) => setRole(u.id, e.target.value)} style={{ width: 130 }}>
                  {["admin", "reviewer", "viewer"].map((r) => <option key={r} value={r}>{r}</option>)}
                </select></td></tr>
            ))}</tbody></table>
        </div>
      )}
      {tab === "health" && health && (
        <div className="card">
          <h3>Documents by status</h3>
          <p>{Object.entries(health.documents_by_status || {}).map(([k, v]: any) => `${k}: ${v}`).join(" · ")}</p>
          <p className="small muted">Users: {health.users} · Questions: {health.questions} · Mode: {health.mode}</p>
          {health.failed.length > 0 && health.failed.map((f: any) => (
            <p key={f.id} className="small"><span className="badge badge-bad">Failed</span> {f.title} — {f.error}</p>
          ))}
          {health.failed.length === 0 && <p className="small muted">No failed ingestions.</p>}
        </div>
      )}
      {tab === "audit" && (
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table><thead><tr><th>Time</th><th>Action</th><th>Object</th><th>Detail</th></tr></thead>
            <tbody>{(audit || []).map((a: any) => (
              <tr key={a.id}><td className="small">{a.created_at}</td><td>{a.action}</td><td className="small">{a.object_type} {a.object_id.slice(0, 8)}</td><td className="small">{a.detail}</td></tr>
            ))}</tbody></table>
        </div>
      )}
    </div>
  );
}

function Settings({ user, onUser, theme, toggleTheme, onLogout }: any) {
  const [name, setName] = useState(user.name);
  const [cur, setCur] = useState("");
  const [npw, setNpw] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  async function saveProfile() {
    // Profile name update is not a separate endpoint in v1; verify-email stub + password change are.
    setMsg("Profile editing (name) is not a v1 endpoint — name is shown from registration. Use change password below, or theme toggle.");
  }
  async function changePw() {
    setErr(""); setMsg("");
    try { await api("/api/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: cur, new_password: npw }) }); setMsg("Password changed."); setCur(""); setNpw(""); }
    catch (e: any) { setErr(e.message); }
  }
  async function verify() {
    try { const r = await api("/api/auth/verify-email", { method: "POST" }); setMsg(r.note || "Verified."); onUser({ ...user, email_verified: true }); }
    catch (e: any) { setErr(e.message); }
  }
  return (
    <div className="grid grid-2">
      <div className="card">
        <h3>Profile</h3>
        <dl className="kv"><dt>Name</dt><dd>{user.name}</dd><dt>Email</dt><dd>{user.email}</dd><dt>Role</dt><dd>{user.role}</dd><dt>Email verified</dt><dd>{user.email_verified ? "Yes" : "No (stub — click Verify below)"}</dd></dl>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
          <button className="btn" onClick={saveProfile}>Save</button>
          <button className="btn" onClick={verify}>Verify email (stub)</button>
        </div>
      </div>
      <div className="card">
        <h3>Change password</h3>
        <input type="password" placeholder="Current password" value={cur} onChange={(e) => setCur(e.target.value)} style={{ marginBottom: 8 }} />
        <input type="password" placeholder="New password (min 8 chars)" value={npw} onChange={(e) => setNpw(e.target.value)} style={{ marginBottom: 8 }} />
        <button className="btn btn-primary" onClick={changePw}>Change password</button>
        <Err msg={err} />{msg && <p style={{ color: "var(--green)" }}>{msg}</p>}
      </div>
      <div className="card">
        <h3>Appearance</h3>
        <p className="muted small">Current theme: {theme}</p>
        <button className="btn" onClick={toggleTheme}>Switch to {theme === "light" ? "dark" : "light"} mode</button>
      </div>
      <div className="card">
        <h3>Session</h3>
        <p className="muted small">Tokens are stateless JWTs (7-day expiry). Logout clears the token on this device.</p>
        <button className="btn" onClick={onLogout}>Logout</button>
      </div>
    </div>
  );
}

// ---------- Root ----------
export default function App() {
  const { theme, toggle } = useTheme();
  const [route, setRoute] = useState<"landing" | "auth" | "app">(savedToken() ? "app" : "landing");
  const [user, setUser] = useState<any>(null);
  const [view, setView] = useState<View>("overview");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (savedToken()) {
      api("/api/auth/me").then((u) => { setUser(u); setRoute("app"); })
        .catch(() => { saveToken(null); setRoute("landing"); });
    }
  }, []);

  function logout() {
    api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    saveToken(null); setUser(null); setRoute("landing");
  }

  if (route === "landing") return <Landing onStart={() => setRoute("auth")} onLogin={() => setRoute("auth")} />;
  if (route === "auth") return <Auth onAuthed={(u) => { setUser(u); setRoute("app"); setView("overview"); }} goLanding={() => setRoute("landing")} />;
  if (!user) return <p style={{ padding: 24 }}>Loading session…</p>;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="logo">Reg<span style={{ color: "#60a5fa" }}>Lens</span></div>
        {NAV.map(([v, label]) => (
          <button key={v} className={view === v ? "active" : ""} onClick={() => setView(v as View)}>{label}</button>
        ))}
        <div style={{ marginTop: "auto", padding: "12px 10px", fontSize: 13 }}>
          <div>{user.name}</div>
          <div className="muted" style={{ color: "#94a3b8" }}>{user.email} · {user.role}</div>
          <button onClick={toggle} style={{ marginTop: 8 }}>Theme: {theme} ⇄</button>
          <button onClick={logout} style={{ marginTop: 4 }}>Logout</button>
        </div>
      </aside>
      <main className="main">
        <div className="topbar">
          <h1>{NAV.find(([v]) => v === view)?.[1]}</h1>
          {view === "admin" && user.role !== "admin" && <span className="badge badge-warn">Admin only — you are {user.role}; evaluation &amp; user management are restricted.</span>}
        </div>
        <Err msg={err} />
        {view === "overview" && <Overview user={user} />}
        {view === "library" && <Library />}
        {view === "upload" && (user.role === "viewer" ? <p className="muted">Viewers cannot upload documents. Ask an Admin or Reviewer to upload, or ask for a role change.</p> : <Upload />)}
        {view === "ask" && <Ask />}
        {view === "compare" && <Compare />}
        {view === "conflicts" && <Conflicts />}
        {view === "obligations" && <Obligations />}
        {view === "graph" && <Graph />}
        {view === "history" && <History />}
        {view === "evidence" && <Evidence />}
        {view === "admin" && (user.role === "admin" ? <Admin /> : <p className="muted">Admin only. You are signed in as {user.role} — evaluation runs, user management, ingestion health and audit logs need the Admin role.</p>)}
        {view === "settings" && <Settings user={user} onUser={setUser} theme={theme} toggleTheme={toggle} onLogout={logout} />}
      </main>
    </div>
  );
}
