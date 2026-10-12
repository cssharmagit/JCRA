import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import {
  answerQuestion,
  deleteClaim,
  deleteExpense,
  getClaim,
  getExpenseDetail,
  getInsights,
  listClaims,
  listConversations,
  newClaim,
  openClaim,
  overrideExpense,
  reopenClaim,
  renameClaim,
  sendMessage,
  submitClaim,
  uploadFiles,
  type Claim,
  type ClaimSummary,
  type Conversation,
  type ExpenseDetail,
  type Insights,
} from "./api";

type IconName =
  | "spark"
  | "grid"
  | "receipt"
  | "card"
  | "chart"
  | "users"
  | "settings"
  | "bell"
  | "chevron"
  | "upload"
  | "check"
  | "alert"
  | "file"
  | "send"
  | "paperclip"
  | "more"
  | "search"
  | "arrow";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    spark: <path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3ZM5.5 14l.7 2.3 2.3.7-2.3.7L5.5 20l-.7-2.3-2.3-.7 2.3-.7.7-2.3Z" />,
    grid: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></>,
    receipt: <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Zm3 5h6m-6 4h6" />,
    card: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M3 10h18m-14 5h4" /></>,
    chart: <path d="M4 19V9m6 10V5m6 14v-7m4 7H2" />,
    users: <><path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 20v-2a4 4 0 0 0-3-3.9m-2-10a4 4 0 0 1 0 7.8" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
    bell: <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 13h4" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    upload: <path d="M12 16V4m0 0L7 9m5-5 5 5M5 14v5h14v-5" />,
    check: <path d="m5 12 4 4L19 6" />,
    alert: <><path d="M12 9v4m0 4h.01" /><path d="M10.3 4.1 2.6 18a2 2 0 0 0 1.8 3h15.2a2 2 0 0 0 1.8-3L13.7 4.1a2 2 0 0 0-3.4 0Z" /></>,
    file: <><path d="M6 2h8l4 4v16H6V2Z" /><path d="M14 2v5h5M9 13h6m-6 4h5" /></>,
    send: <path d="m22 2-7 20-4-9-9-4 20-7Zm-11 11L22 2" />,
    paperclip: <path d="m21.4 11.6-8.9 8.9a6 6 0 0 1-8.5-8.5l9.6-9.6a4 4 0 0 1 5.7 5.7l-9.6 9.6a2 2 0 0 1-2.8-2.8L16 5.8" />,
    more: <><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function Button({ children, className = "", ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={className} {...rest}>{children}</button>;
}

function FilePicker({ disabled, busy, onPick, onFiles }: { disabled: boolean; busy: boolean; onPick: () => void; onFiles: (files: FileList) => void }) {
  return (
    <Button
      className="upload-zone"
      type="button"
      disabled={disabled}
      onClick={onPick}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        if (!disabled && event.dataTransfer.files?.length) onFiles(event.dataTransfer.files);
      }}
    >
      <span className="upload-icon"><Icon name="upload" /></span>
      <span>
        <strong>{busy ? "Reading your receipts…" : "Drop receipts here"}</strong>
        <small>{busy ? "Large files with many receipts can take a minute or two." : "or choose photos, PDFs, and text bills"}</small>
      </span>
      <span className="choose-files">{busy ? "Working…" : "Choose files"}</span>
    </Button>
  );
}

const PROMPTS = ["What does the meal policy cover?", "Explain the claim total"];

export default function App() {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "attention" | "ready">("all");
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [claimsOpen, setClaimsOpen] = useState(false);
  const [detail, setDetail] = useState<ExpenseDetail | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [tableView, setTableView] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number; filename: string } | null>(null);
  const [chatWidth, setChatWidth] = useState(() => Number(localStorage.getItem("jrca-chat-width")) || 365);
  const [chatFocus, setChatFocus] = useState(false);
  const [view, setView] = useState<"expenses" | "overview" | "cards" | "insights" | "settings">("expenses");
  const [sidebarHidden, setSidebarHidden] = useState(false);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [adminToken, setAdminToken] = useState("");
  const [tokenPromptOpen, setTokenPromptOpen] = useState(false);
  const [tokenDraft, setTokenDraft] = useState("");
  const [editingPolicy, setEditingPolicy] = useState(false);
  const [policyDraft, setPolicyDraft] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyQuery, setHistoryQuery] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [openConversation, setOpenConversation] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const answerRef = useRef<HTMLInputElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const busyRef = useRef(false);
  const stopRef = useRef(false);
  busyRef.current = busy;

  function pickFiles() {
    if (!busyRef.current) fileRef.current?.click();
  }

  function startResize(event: React.PointerEvent) {
    event.preventDefault();
    const onMove = (move: PointerEvent) => {
      const width = Math.min(640, Math.max(300, window.innerWidth - move.clientX));
      setChatWidth(width);
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      setChatWidth((width) => {
        localStorage.setItem("jrca-chat-width", String(width));
        return width;
      });
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  async function uploadSequentially(files: File[]) {
    setBusy(true);
    setError("");
    stopRef.current = false;
    let lastClaim: Claim | null = null;
    const skipped: string[] = [];
    for (let index = 0; index < files.length; index += 1) {
      if (stopRef.current) {
        skipped.push(...files.slice(index).map((file) => file.name));
        break;
      }
      setProgress({ current: index + 1, total: files.length, filename: files[index].name });
      try {
        lastClaim = await uploadFiles([files[index]]);
        setClaim(lastClaim);
      } catch (caught) {
        setError(`${files[index].name}: ${caught instanceof Error ? caught.message : "failed"}`);
      }
    }
    setProgress(null);
    setBusy(false);
    if (skipped.length) setError(`Stopped. Not processed: ${skipped.join(", ")}. The receipts already read are saved.`);
  }

  async function refreshClaims() {
    try {
      setClaims((await listClaims()).claims);
    } catch {
      /* non-fatal */
    }
  }

  function openDetail(id: string) {
    getExpenseDetail(id)
      .then(setDetail)
      .catch(() => setError("Could not load that expense."));
  }

  async function run(work: () => Promise<Claim>) {
    setBusy(true);
    setError("");
    try {
      const next = await work();
      setClaim(next);
      if (next.uiAction === "focus_chat") setChatFocus(true);
      if (next.uiAction === "show_expenses") { setChatFocus(false); setView("expenses"); }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void run(getClaim);
    void refreshClaims();
  }, []);

  useEffect(() => {
    // stop the browser from opening files dropped outside the upload zone
    const prevent = (event: DragEvent) => event.preventDefault();
    window.addEventListener("dragover", prevent);
    window.addEventListener("drop", prevent);
    return () => {
      window.removeEventListener("dragover", prevent);
      window.removeEventListener("drop", prevent);
    };
  }, []);

  useEffect(() => {
    if (claimsOpen) void refreshClaims();
  }, [claimsOpen, claim?.id, claim?.status]);

  useEffect(() => {
    if (view === "insights" || view === "overview" || view === "cards") {
      getInsights().then(setInsights).catch(() => setInsights(null));
      void refreshClaims();
    }
    if (view === "settings") {
      fetch("/api/admin/config").then((response) => response.json()).then(setConfig).catch(() => setConfig(null));
    }
  }, [view, claim?.id, claim?.status, claim?.summary.processed]);

  useEffect(() => {
    // keep the conversation pinned to the latest message
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight });
  }, [claim?.messages.length, busy]);

  useEffect(() => {
    if (!historyOpen) return;
    const handle = setTimeout(() => {
      listConversations(historyQuery.trim() || undefined)
        .then((data) => setConversations(data.conversations))
        .catch(() => setConversations([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [historyOpen, historyQuery]);

  const query = search.trim().toLowerCase();
  const visible = (claim?.expenses ?? []).filter((expense) => {
    if (activeTab === "attention" && expense.status !== "attention") return false;
    if (activeTab === "ready" && expense.status !== "ready") return false;
    if (!query) return true;
    return [expense.merchant, expense.meta, expense.amount, expense.policyLabel]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
  const lastMessageId = claim?.messages.length ? claim.messages[claim.messages.length - 1].id : "";
  const submitted = claim?.status === "SUBMITTED";
  const ready = Boolean(claim?.submittable);
  const question = claim?.openQuestion ?? null;

  function focusAnswer() {
    answerRef.current?.focus();
    document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <div className="app-shell">
      <input
        ref={fileRef}
        style={{ display: "none" }}
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp,.pdf,.txt"
        onChange={(event) => {
          const files = event.target.files;
          if (files?.length && !busyRef.current) {
            void uploadSequentially(Array.from(files));
          }
          event.target.value = "";
        }}
      />
      <aside className={`sidebar ${sidebarHidden ? "hidden" : ""}`}>
        <div className="brand" title="Jio Reimbursement Claims Assistant"><span><Icon name="spark" size={20} /></span><b>JRCA</b></div>
        <nav className="main-nav" aria-label="Main navigation">
          <Button className={`nav-item ${view === "overview" ? "active" : ""}`} type="button" onClick={() => setView("overview")}><Icon name="grid" /><span>Overview</span></Button>
          <Button className={`nav-item ${view === "expenses" ? "active" : ""}`} type="button" onClick={() => setView("expenses")}><Icon name="receipt" /><span>Expenses</span><small>{claim?.summary.processed ?? 0}</small></Button>
          <Button className={`nav-item ${view === "cards" ? "active" : ""}`} type="button" onClick={() => setView("cards")}><Icon name="card" /><span>Claims</span></Button>
          <Button className={`nav-item ${view === "insights" ? "active" : ""}`} type="button" onClick={() => setView("insights")}><Icon name="chart" /><span>Insights</span></Button>
        </nav>
        <div className="sidebar-label">Workspace</div>
        <nav className="main-nav secondary">
          <Button className={`nav-item ${view === "settings" ? "active" : ""}`} type="button" onClick={() => setView("settings")}><Icon name="settings" /><span>Settings</span></Button>
        </nav>
        <div className="sidebar-spacer" />
        <div className="support-card">
          <span className="support-icon"><Icon name="spark" size={16} /></span>
          <strong>Need a hand?</strong>
          <p>Ask your expense assistant anything.</p>
          <Button type="button" onClick={() => document.getElementById("assistant")?.scrollIntoView({ behavior: "smooth" })}>Open assistant <Icon name="arrow" size={15} /></Button>
        </div>
        <div className="profile">
          <div className="avatar">{(claim?.employee?.name ?? "Chandra Sharma").split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase()}</div>
          <div><strong>{claim?.employee?.name ?? "Chandra Sharma"}</strong><small>{claim?.employee?.dept ?? "Engineering"}</small></div>
          <Icon name="more" />
        </div>
      </aside>

      <main className={`workspace ${sidebarHidden ? "full" : ""}`}>
        <header className="topbar">
          <Button className="icon-button" type="button" aria-label="Toggle sidebar" title="Hide or show the menu" onClick={() => setSidebarHidden((value) => !value)}><Icon name="chevron" size={16} /></Button>
          <div className="mobile-brand"><Icon name="spark" size={17} /> JRCA</div>
          <div className="breadcrumbs"><span>{view === "expenses" ? "Expenses" : view[0].toUpperCase() + view.slice(1)}</span><Icon name="chevron" size={14} /><strong>{claim?.title ?? "Expenses"}</strong></div>
          <div className="top-actions">
            {searchOpen && (
              <input
                ref={searchRef}
                className="search-input"
                value={search}
                placeholder="Search receipts…"
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setSearch("");
                    setSearchOpen(false);
                  }
                }}
                aria-label="Search receipts"
              />
            )}
            <Button
              className="icon-button"
              type="button"
              aria-label="Search"
              onClick={() => {
                setSearchOpen((open) => {
                  if (open) setSearch("");
                  return !open;
                });
                setTimeout(() => searchRef.current?.focus(), 0);
              }}
            >
              <Icon name="search" />
            </Button>
            <Button className="icon-button notification" type="button" aria-label="Notifications"><Icon name="bell" /></Button>
          </div>
        </header>

        <div className={`content-wrap ${chatFocus ? "chat-focus" : ""}`} style={{ "--chat-width": `${chatWidth}px` } as React.CSSProperties}>
          {view === "overview" && (
            <section className="claim-column">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">Workspace</div>
                  <div className="title" role="heading" aria-level={1}>Overview</div>
                  <p>Everything across your claims at a glance.</p>
                </div>
              </div>
              <div className="overview-grid">
                <div className="stat-card"><span>Total claimed</span><strong>{insights ? `${insights.currency === "INR" ? "₹" : insights.currency + " "}${insights.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}</strong></div>
                <div className="stat-card"><span>Claims</span><strong>{insights?.claimCount ?? "—"}</strong></div>
                <div className="stat-card"><span>Receipts</span><strong>{insights?.expenseCount ?? "—"}</strong></div>
                <div className="stat-card"><span>Drafts</span><strong>{claims.filter((item) => item.status !== "SUBMITTED").length}</strong></div>
              </div>
              <div className="section-title" role="heading" aria-level={2} style={{ margin: "22px 0 10px" }}>Recent claims</div>
              <div className="drawer-list">
                {claims.slice(0, 6).map((item) => (
                  <div key={item.id} className="drawer-row">
                    <Button type="button" className="drawer-open" disabled={busy} onClick={() => { setView("expenses"); void run(() => openClaim(item.id)); }}>
                      <strong>{item.title}</strong>
                      <small>{item.status === "SUBMITTED" ? "Submitted" : "Draft"} · {item.expenseCount} receipt{item.expenseCount === 1 ? "" : "s"}</small>
                    </Button>
                  </div>
                ))}
              </div>
            </section>
          )}

          {view === "cards" && (
            <section className="claim-column">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">Workspace</div>
                  <div className="title" role="heading" aria-level={1}>Claims</div>
                  <p>Open a claim to work on it, reopen a submitted one, or clean up drafts.</p>
                </div>
                <div className="heading-actions">
                  <Button className="ghost-button" type="button" disabled={busy} onClick={() => void run(newClaim).then(refreshClaims).then(() => setView("expenses"))}>New claim</Button>
                </div>
              </div>
              <div className="drawer-list">
                {claims.map((item) => (
                  <div key={item.id} className={`drawer-row ${item.id === claim?.id ? "current" : ""}`}>
                    <Button type="button" className="drawer-open" disabled={busy} onClick={() => { setView("expenses"); void run(() => openClaim(item.id)); }}>
                      <strong>{item.title}</strong>
                      <small>{item.status === "SUBMITTED" ? "Submitted · view only" : "Draft · editable"} · {item.expenseCount} receipt{item.expenseCount === 1 ? "" : "s"}</small>
                    </Button>
                    {item.status === "SUBMITTED" ? (
                      <Button type="button" className="drawer-delete" disabled={busy} onClick={() => {
                        if (window.confirm(`Reopen "${item.title}" for editing? It will leave the finance queue until resubmitted.`)) {
                          setView("expenses");
                          void run(() => reopenClaim(item.id)).then(refreshClaims);
                        }
                      }}>Reopen</Button>
                    ) : (
                      <Button type="button" className="drawer-delete" disabled={busy} onClick={() => {
                        if (window.confirm(`Delete "${item.title}" and its receipts?`)) void run(() => deleteClaim(item.id)).then(refreshClaims);
                      }}>Delete</Button>
                    )}
                  </div>
                ))}
                {!claims.length && <div className="drawer-empty">No claims yet.</div>}
              </div>
            </section>
          )}

          {view === "insights" && (
            <section className="claim-column">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">Workspace</div>
                  <div className="title" role="heading" aria-level={1}>Insights</div>
                  <p>Where the money goes, across all claims, in {insights?.currency ?? "your home currency"}.</p>
                </div>
              </div>
              {insights && insights.byCategory.length ? (
                <>
                  <div className="section-title" role="heading" aria-level={2} style={{ margin: "4px 0 10px" }}>Spend by category</div>
                  <div className="insight-bars">
                    {insights.byCategory.map((row) => (
                      <div key={row.category} className="insight-bar">
                        <span>{row.category}</span>
                        <div className="bar-track"><i style={{ width: `${Math.max(4, (row.total / insights.byCategory[0].total) * 100)}%` }} /></div>
                        <strong>{row.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                      </div>
                    ))}
                  </div>
                  <div className="section-title" role="heading" aria-level={2} style={{ margin: "24px 0 10px" }}>Spend by claim</div>
                  <div className="insight-bars">
                    {insights.byClaim.filter((row) => row.total > 0).map((row) => (
                      <div key={row.id} className="insight-bar">
                        <span>{row.title}</span>
                        <div className="bar-track"><i style={{ width: `${Math.max(4, (row.total / Math.max(...insights.byClaim.map((entry) => entry.total), 1)) * 100)}%` }} /></div>
                        <strong>{row.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="empty-state"><Icon name="chart" /> No spend recorded yet. Add receipts to a claim first.</div>
              )}
            </section>
          )}

          {view === "settings" && (
            <section className="claim-column">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">Workspace</div>
                  <div className="title" role="heading" aria-level={1}>Settings</div>
                  <p>{config?.admin_enabled ? (adminToken ? "Admin unlocked — you can change the configuration." : "Read-only. Unlock with the admin token to make changes.") : "Admin token not configured — changes are open (development mode)."}</p>
                </div>
                {Boolean(config?.admin_enabled) && (
                  adminToken ? (
                    <Button className="ghost-button" type="button" onClick={() => { setAdminToken(""); setEditingPolicy(false); }}>Lock admin</Button>
                  ) : (
                    <Button className="ghost-button" type="button" onClick={() => { setTokenDraft(""); setTokenPromptOpen(true); }}>Unlock admin</Button>
                  )
                )}
              </div>
              {tokenPromptOpen && !adminToken && (
                <form
                  className="token-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const token = tokenDraft.trim();
                    if (!token) return;
                    fetch("/api/admin/verify", { method: "POST", headers: { "X-Admin-Token": token } })
                      .then((response) => {
                        if (response.ok) {
                          setAdminToken(token);
                          setTokenPromptOpen(false);
                        } else {
                          setError("That admin token is not valid.");
                        }
                      })
                      .catch(() => setError("Could not verify the admin token."));
                  }}
                >
                  <input
                    type="password"
                    className="history-search"
                    style={{ marginBottom: 0 }}
                    value={tokenDraft}
                    autoFocus
                    placeholder="Admin token"
                    onChange={(event) => setTokenDraft(event.target.value)}
                    onKeyDown={(event) => { if (event.key === "Escape") setTokenPromptOpen(false); }}
                    aria-label="Admin token"
                  />
                  <Button className="ghost-button" type="submit" disabled={!tokenDraft.trim()}>Verify</Button>
                  <Button className="ghost-button" type="button" onClick={() => setTokenPromptOpen(false)}>Cancel</Button>
                </form>
              )}
              {config ? (
                <div className="settings-list">
                  <div><span>Signed-in employee</span><strong>{String(config.employee_name)} · {String(config.employee_dept)}</strong></div>
                  <div><span>Home currency</span><strong>{String(config.home_currency)}</strong></div>
                  <div><span>Conversion rates</span><strong>{Object.entries((config.fx_rates as Record<string, number>) ?? {}).map(([code, rate]) => `${code} ${rate}`).join(" · ") || "None"}</strong></div>
                  <div><span>Upload limits</span><strong>{String(config.max_files)} files · {String(config.max_file_mb)} MB each</strong></div>
                  <div><span>Model provider</span><strong>{String(config.provider)}</strong></div>
                  <div><span>Admin access</span><strong>{config.admin_enabled ? (adminToken ? "Unlocked for this session" : "Locked · token required for changes") : "Open (no token configured)"}</strong></div>
                  <div className="policy-block">
                    <span>Company policy</span>
                    <p className="policy-note">
                      The policy is written in plain language and <b>interpreted by the AI model</b> when it judges each receipt — edit the text and the next receipt follows it, no code change needed.
                      A few hard guardrails are <b>enforced deterministically in code</b> and cannot be talked around: a claim cannot be submitted when any receipt is missing its merchant, date, or amount; submitted claims are locked; date math (future / older than 24 months) is computed by code; human overrides are audited.
                    </p>
                    {editingPolicy ? (
                      <>
                        <textarea className="policy-editor" value={policyDraft} rows={14} onChange={(event) => setPolicyDraft(event.target.value)} />
                        <div className="policy-actions">
                          <Button className="ghost-button" type="button" onClick={() => setEditingPolicy(false)}>Cancel</Button>
                          <Button
                            className="ghost-button"
                            type="button"
                            disabled={policyDraft.trim().length < 20}
                            onClick={() => {
                              const headers: Record<string, string> = { "Content-Type": "application/json" };
                              if (adminToken) headers["X-Admin-Token"] = adminToken;
                              fetch("/api/admin/policy", { method: "PUT", headers, body: JSON.stringify({ text: policyDraft }) })
                                .then(async (response) => {
                                  if (!response.ok) throw new Error((await response.json()).detail ?? "Failed");
                                  setEditingPolicy(false);
                                  return fetch("/api/admin/config").then((r) => r.json()).then(setConfig);
                                })
                                .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not save the policy."));
                            }}
                          >
                            Save policy
                          </Button>
                        </div>
                      </>
                    ) : (
                      <>
                        <pre>{String(config.policy_text)}</pre>
                        {(!config.admin_enabled || adminToken) && (
                          <div className="policy-actions">
                            <Button className="ghost-button" type="button" onClick={() => { setPolicyDraft(String(config.policy_text)); setEditingPolicy(true); }}>Edit policy</Button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div className="empty-state"><Icon name="settings" /> Loading configuration…</div>
              )}
            </section>
          )}

          {view === "expenses" && (
          <section className="claim-column">
            <div className="page-heading">
              <div>
                <div className="eyebrow">Expense claim · {submitted ? "Submitted" : ready ? "Ready" : "Draft"}</div>
                {renaming ? (
                  <form
                    className="rename-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const title = titleDraft.trim();
                      setRenaming(false);
                      if (title && title !== claim?.title) void run(() => renameClaim(title)).then(refreshClaims);
                    }}
                  >
                    <input
                      className="rename-input"
                      value={titleDraft}
                      autoFocus
                      maxLength={80}
                      onChange={(event) => setTitleDraft(event.target.value)}
                      onKeyDown={(event) => { if (event.key === "Escape") setRenaming(false); }}
                      aria-label="Claim name"
                    />
                    <Button className="ghost-button" type="submit" disabled={busy}>Save</Button>
                  </form>
                ) : (
                  <div
                    className={`title ${submitted ? "" : "editable"}`}
                    role="heading"
                    aria-level={1}
                    title={submitted ? undefined : "Click to rename"}
                    onClick={() => {
                      if (submitted || !claim) return;
                      setTitleDraft(claim.title);
                      setRenaming(true);
                    }}
                  >
                    {claim?.title ?? "Loading your claim"}
                    {!submitted && claim && <span className="rename-hint">✎</span>}
                  </div>
                )}
                <p>{claim?.subtitle ?? "The assistant is opening your draft."}</p>
              </div>
              <div className="heading-actions">
                <Button className="ghost-button" type="button" onClick={() => setClaimsOpen(true)}>My claims</Button>
                <Button className="ghost-button" type="button" disabled={busy} onClick={() => void run(newClaim).then(refreshClaims)}>New claim</Button>
              </div>
            </div>

            {error && (
              <div className="error-banner" role="alert">
                <span>{error}</span>
                <Button type="button" onClick={() => void run(getClaim)}>Retry</Button>
              </div>
            )}

            <div className="status-card" role="status" aria-live="polite">
              <div className="status-copy">
                <div className={`status-mark ${ready || submitted ? "complete" : ""}`}><Icon name={ready || submitted ? "check" : "spark"} size={19} /></div>
                <div>
                  <strong>{busy ? "Working through your receipts" : claim?.headline ?? "Drop your receipts"}</strong>
                  <p>{busy ? "Reading, categorizing, and checking policy." : claim?.detail ?? "Photos, PDFs, or text bills all work."}</p>
                </div>
              </div>
              <div className="readiness">
                <span>{claim ? `${claim.readiness}%` : "—"}</span>
                <div className="progress"><i style={{ width: `${claim?.readiness ?? 0}%` }} /></div>
              </div>
            </div>

            {question && !submitted && (
              <form
                className="attention-card"
                onSubmit={(event) => {
                  event.preventDefault();
                  const text = answer.trim();
                  if (!text) return;
                  setAnswer("");
                  void run(() => answerQuestion(question.id, text));
                }}
              >
                <div className="attention-main">
                  <span className="warning-icon"><Icon name="alert" size={18} /></span>
                  <div>
                    <span className="attention-label">
                      Needs your input
                      {(() => {
                        const target = claim?.expenses.find((item) => item.id === question.expenseId);
                        return target ? ` · ${target.merchant} · ${target.amount}` : "";
                      })()}
                    </span>
                    <strong>{question.prompt}</strong>
                    <p>{question.reason}</p>
                  </div>
                  <Button className="ghost-button small" type="button" onClick={() => openDetail(question.expenseId)}>View receipt</Button>
                </div>
                {question.field === "duplicate" ? (
                  <div className="attention-actions">
                    <Button className="resolve-button" type="button" disabled={busy} onClick={() => void run(() => answerQuestion(question.id, "Yes, it is a separate charge. Keep it."))}>Keep — separate charge</Button>
                    <Button className="ghost-button" type="button" disabled={busy} onClick={() => void run(() => answerQuestion(question.id, "Remove the duplicate receipt."))}>Remove duplicate</Button>
                  </div>
                ) : (
                  <div className="attention-actions">
                    <input
                      id="answer-input"
                      ref={answerRef}
                      className="answer-input"
                      value={answer}
                      placeholder="Type the missing detail"
                      onChange={(event) => setAnswer(event.target.value)}
                      disabled={busy}
                    />
                    <Button className="resolve-button" type="submit" disabled={busy || !answer.trim()}>Add details <Icon name="arrow" size={15} /></Button>
                  </div>
                )}
              </form>
            )}

            {claim?.notice && <div className="upload-toast"><Icon name="check" size={16} /> {claim.notice}</div>}

            <FilePicker disabled={busy || submitted} busy={busy} onPick={pickFiles} onFiles={(files) => void uploadSequentially(Array.from(files))} />

            {progress && (
              <div className="progress-banner" role="status">
                <span className="progress-spinner" />
                <span>Reading file {progress.current} of {progress.total}: <strong>{progress.filename}</strong>. Multi-receipt files take longer — each receipt is checked against policy.</span>
                <Button type="button" onClick={() => { stopRef.current = true; }}>Stop after this file</Button>
              </div>
            )}

            <div className="expense-header">
              <div>
                <div className="section-title" role="heading" aria-level={2}>Expenses</div>
                <span>{claim?.summary.processed ?? 0} items · {claim?.total ?? "$0.00"}</span>
              </div>
              <div className="tabs" role="tablist">
                <Button type="button" className={activeTab === "all" ? "active" : ""} onClick={() => setActiveTab("all")}>All <i>{claim?.summary.processed ?? 0}</i></Button>
                <Button type="button" className={activeTab === "attention" ? "active" : ""} onClick={() => setActiveTab("attention")}>Needs attention <i>{claim?.summary.needsReview ?? 0}</i></Button>
                <Button type="button" className={activeTab === "ready" ? "active" : ""} onClick={() => setActiveTab("ready")}>Ready <i>{claim?.summary.ready ?? 0}</i></Button>
                <Button type="button" className={tableView ? "active" : ""} onClick={() => setTableView((value) => !value)} aria-label="Toggle table view">Table</Button>
                <Button type="button" onClick={() => { window.location.href = "/api/claims/active/export.csv"; }} aria-label="Download CSV">CSV</Button>
                <Button type="button" onClick={() => { window.location.href = "/api/claims/active/export.json"; }} aria-label="Download JSON">JSON</Button>
              </div>
            </div>

            {tableView ? (
              <div className="expense-table-wrap">
                <table className="expense-table">
                  <thead>
                    <tr><th>Merchant</th><th>Date · Category</th><th>Status</th><th className="num">Amount</th></tr>
                  </thead>
                  <tbody>
                    {visible.map((expense) => (
                      <tr key={expense.id} onClick={() => openDetail(expense.id)}>
                        <td>{expense.merchant}</td>
                        <td>{expense.meta}</td>
                        <td><span className={expense.status === "attention" ? "cell-warn" : "cell-ok"}>{expense.policyLabel}</span></td>
                        <td className="num">{expense.amount}</td>
                      </tr>
                    ))}
                    {!visible.length && (
                      <tr><td colSpan={4} className="table-empty">{query ? `No receipts match “${search.trim()}”.` : "No receipts yet."}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
            <div className="expense-list">
              {visible.length ? visible.map((expense) => {
                const needsAttention = expense.status === "attention";
                return (
                  <Button className="expense-row" type="button" key={expense.id} onClick={() => openDetail(expense.id)}>
                    <span className={`merchant-logo ${expense.tone}`}>{expense.mark}</span>
                    <span className="expense-name"><strong>{expense.merchant}</strong><small>{expense.meta}</small></span>
                    <span className="policy-state">
                      <i className={needsAttention ? "warn" : ""}><Icon name={needsAttention ? "alert" : "check"} size={12} /></i>
                      {expense.policyLabel}
                    </span>
                    <strong className="amount">{expense.amount}</strong>
                    <Icon name="chevron" size={16} />
                  </Button>
                );
              }) : (
                <div className="empty-state"><Icon name={claim?.expenses.length ? (query ? "search" : "check") : "upload"} /> {claim?.expenses.length ? (query ? `No receipts match “${search.trim()}”.` : "Nothing needs your attention.") : "Drop receipts to start this claim."}</div>
              )}
            </div>
            )}

            <footer className="submit-bar">
              <div>
                <span>Claim total</span>
                <strong>{claim?.total ?? "$0.00"} <small>{claim?.currency ?? "USD"}</small></strong>
              </div>
              <div className="submit-note">
                <Icon name={ready || submitted ? "check" : "alert"} size={16} />
                {submitted
                  ? "Submitted to the finance queue"
                  : ready
                    ? claim?.totalNote ?? "All required details are complete"
                    : (claim?.summary.needsReview ?? 0) > 0
                      ? `${claim?.summary.needsReview} receipt${(claim?.summary.needsReview ?? 0) === 1 ? "" : "s"} need${(claim?.summary.needsReview ?? 0) === 1 ? "s" : ""} attention before you can submit`
                      : "Add receipts to build this claim"}
              </div>
              {submitted && (
                <Button className="ghost-button" type="button" disabled={busy} onClick={() => {
                  if (claim && window.confirm("Reopen this claim for editing? It will leave the finance queue until resubmitted.")) {
                    void run(() => reopenClaim(claim.id));
                  }
                }}>Reopen</Button>
              )}
              <Button className={`submit-button ${submitted ? "submitted" : ""}`} disabled={!ready || busy || submitted} onClick={() => void run(submitClaim)}>
                {submitted ? <><Icon name="check" size={17} /> Submitted</> : <>Submit claim <Icon name="arrow" size={17} /></>}
              </Button>
            </footer>
          </section>
          )}

          <div
            className="panel-resizer"
            role="separator"
            aria-label="Resize assistant panel"
            onPointerDown={startResize}
            onDoubleClick={() => { setChatWidth(365); localStorage.setItem("jrca-chat-width", "365"); }}
          />

          <aside className="assistant-panel" id="assistant">
            <div className="assistant-head">
              <div>
                <span className="ai-mark"><Icon name="spark" size={17} /></span>
                <div>
                  <strong>Expense assistant</strong>
                  <small>{claim?.provider === "replay" ? "Demo cognition · add a model key to read photos" : "Working with your claim"}</small>
                </div>
              </div>
              <div className="head-buttons">
                <Button type="button" className="focus-toggle" aria-label="Conversation history" title="All conversations" onClick={() => setHistoryOpen(true)}>History</Button>
                <Button type="button" className={`focus-toggle ${chatFocus ? "active" : ""}`} aria-label="Toggle focus mode" title={chatFocus ? "Show the expense details again" : "Give the chat all the space"} onClick={() => setChatFocus((value) => !value)}>
                  {chatFocus ? "Show detail" : "Focus chat"}
                </Button>
              </div>
            </div>

            <div className="chat-stats">
              <div><strong>{claim?.summary.processed ?? 0}</strong><span>read</span></div>
              <div><strong className="positive">{claim?.summary.ready ?? 0}</strong><span>ready</span></div>
              <div><strong className={claim?.summary.needsReview ? "warning" : "positive"}>{claim?.summary.needsReview ?? 0}</strong><span>review</span></div>
              <div><strong className={claim?.summary.duplicates ? "warning" : undefined}>{claim?.summary.duplicates ?? 0}</strong><span>dupes</span></div>
            </div>

            <div className="assistant-body" ref={threadRef}>
              <div className="thread">
                {(claim?.messages ?? []).map((item) => item.role === "user" ? (
                  <div className="user-line" key={item.id}>{item.content}</div>
                ) : (
                  <div className="assistant-message" key={item.id}>
                    <div className="mini-ai"><Icon name="spark" size={13} /></div>
                    <div>
                      <p>
                        {(() => {
                          const match = item.content.match(/(\/api\/claims\/active\/export\.(json|csv)\S*)/);
                          if (!match) return item.content;
                          return (<>{item.content.slice(0, match.index)}<a href={match[1]}>Download {match[2].toUpperCase()}</a></>);
                        })()}
                      </p>
                      {question && item.id === lastMessageId && (
                        <Button type="button" onClick={focusAnswer}>Review missing detail <Icon name="arrow" size={14} /></Button>
                      )}
                    </div>
                  </div>
                ))}
                {busy && <div className="busy-pill">Thinking…</div>}
              </div>

              <div className="quick-prompts">
                <span>Try asking</span>
                {PROMPTS.map((prompt) => (
                  <Button key={prompt} type="button" disabled={busy} onClick={() => void run(() => sendMessage(prompt))}>{prompt}</Button>
                ))}
              </div>
            </div>

            <form
              className="composer"
              onSubmit={(event) => {
                event.preventDefault();
                const text = message.trim();
                if (!text) return;
                setMessage("");
                void run(() => sendMessage(text));
              }}
            >
              <div className="composer-box">
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  placeholder="Ask about this claim…"
                  rows={2}
                  disabled={busy}
                />
                <div>
                  <Button className="attach-button" type="button" aria-label="Attach receipts" disabled={busy || submitted} onClick={pickFiles}><Icon name="paperclip" size={17} /></Button>
                  <Button className="send-button" type="submit" disabled={busy || !message.trim()} aria-label="Send"><Icon name="send" size={16} /></Button>
                </div>
              </div>
              <small>AI can make mistakes. Review important details.</small>
            </form>
          </aside>
        </div>
      </main>

      {claimsOpen && (
        <div className="drawer-scrim" onClick={() => setClaimsOpen(false)}>
          <aside className="drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <strong>My claims</strong>
              <Button type="button" aria-label="Close" onClick={() => setClaimsOpen(false)}>✕</Button>
            </div>
            <Button className="drawer-new" type="button" disabled={busy} onClick={() => { setClaimsOpen(false); void run(newClaim).then(refreshClaims); }}>
              <Icon name="upload" size={15} /> Start a new claim
            </Button>
            <div className="drawer-list">
              {claims.map((item) => (
                <div key={item.id} className={`drawer-row ${item.id === claim?.id ? "current" : ""}`}>
                  <Button
                    type="button"
                    className="drawer-open"
                    disabled={busy}
                    onClick={() => { setClaimsOpen(false); void run(() => openClaim(item.id)); }}
                  >
                    <strong>{item.title}</strong>
                    <small>{item.status === "SUBMITTED" ? "Submitted · view only" : "Draft · editable"} · {item.expenseCount} receipt{item.expenseCount === 1 ? "" : "s"}</small>
                  </Button>
                  {item.status !== "SUBMITTED" && (
                    <Button
                      type="button"
                      className="drawer-delete"
                      aria-label={`Delete ${item.title}`}
                      disabled={busy}
                      onClick={() => {
                        if (window.confirm(`Delete "${item.title}" and its receipts?`)) {
                          void run(() => deleteClaim(item.id)).then(refreshClaims);
                        }
                      }}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              ))}
              {!claims.length && <div className="drawer-empty">No claims yet.</div>}
            </div>
          </aside>
        </div>
      )}

      {detail && (
        <div className="drawer-scrim" onClick={() => setDetail(null)}>
          <aside className="drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <strong>{detail.merchant ?? "Receipt"}</strong>
              <Button type="button" aria-label="Close" onClick={() => setDetail(null)}>✕</Button>
            </div>
            <div className="detail-grid">
              <div><span>Date</span><strong>{detail.date ?? "Missing"}</strong></div>
              <div><span>Amount</span><strong>{detail.amount ? `${detail.currency ?? ""} ${detail.amount}` : "Missing"}</strong></div>
              <div><span>Category</span><strong>{detail.categoryDetail || detail.category || "—"}</strong></div>
              <div><span>Status</span><strong>{detail.status === "ready" ? "Ready" : detail.policyLabel}</strong></div>
              {detail.attendees && <div><span>Attendees</span><strong>{detail.attendees}</strong></div>}
              {detail.purpose && <div><span>Purpose</span><strong>{detail.purpose}</strong></div>}
              {detail.confidence != null && <div><span>Read confidence</span><strong>{Math.round(detail.confidence * 100)}%</strong></div>}
            </div>
            {detail.summary && <p className="detail-summary">{detail.summary}</p>}
            {detail.overrideReason && (
              <div className="detail-flag">Approved with override by {detail.overrideBy}: {detail.overrideReason}</div>
            )}
            {detail.isDuplicate && <div className="detail-flag warn">Possible duplicate — {detail.duplicateReason}</div>}
            {detail.findings.map((finding, index) => (
              <div key={index} className={`detail-flag ${finding.severity === "blocker" ? "warn" : ""}`}>{finding.message}</div>
            ))}
            {detail.missing.map((item, index) => (
              <div key={index} className="detail-flag">{item.question}</div>
            ))}
            {detail.document && (
              <div className="detail-evidence">
                <div className="drawer-subhead">Evidence · {detail.document.filename}</div>
                {detail.document.mediaType.startsWith("image/") ? (
                  <img src={`/api/claims/active/documents/${detail.document.id}/file`} alt={detail.document.filename} />
                ) : detail.document.mediaType === "application/pdf" ? (
                  <a href={`/api/claims/active/documents/${detail.document.id}/file`} target="_blank" rel="noreferrer" className="evidence-link">Open original PDF</a>
                ) : null}
                {detail.document.extractedText && <pre>{detail.document.extractedText}</pre>}
              </div>
            )}
            {!submitted && detail.status === "attention" && !detail.overrideReason && (
              <Button
                className="ghost-button wide-top"
                type="button"
                disabled={busy}
                onClick={() => {
                  const reason = window.prompt("Approve despite the policy flag. Record the reason (required):");
                  if (reason && reason.trim().length >= 5) {
                    setDetail(null);
                    void run(() => overrideExpense(detail.id, reason.trim()));
                  } else if (reason !== null) {
                    setError("The override reason must be at least 5 characters.");
                  }
                }}
              >
                Approve with override…
              </Button>
            )}
            {!submitted && (
              <Button
                className="drawer-delete wide"
                type="button"
                disabled={busy}
                onClick={() => {
                  if (window.confirm("Remove this receipt from the claim?")) {
                    setDetail(null);
                    void run(() => deleteExpense(detail.id));
                  }
                }}
              >
                Remove this receipt
              </Button>
            )}
          </aside>
        </div>
      )}

      {historyOpen && (
        <div className="drawer-scrim" onClick={() => setHistoryOpen(false)}>
          <aside className="drawer" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <strong>Conversations</strong>
              <Button type="button" aria-label="Close" onClick={() => setHistoryOpen(false)}>✕</Button>
            </div>
            <input
              className="history-search"
              value={historyQuery}
              placeholder="Search all conversations…"
              onChange={(event) => setHistoryQuery(event.target.value)}
              aria-label="Search conversations"
            />
            <div className="drawer-list">
              {conversations.map((item) => (
                <div key={item.claimId} className="conversation-item">
                  <Button
                    type="button"
                    className="drawer-open"
                    onClick={() => setOpenConversation(openConversation === item.claimId ? null : item.claimId)}
                  >
                    <strong>{item.title}</strong>
                    <small>{item.status === "SUBMITTED" ? "Submitted" : "Draft"} · {item.messageCount} message{item.messageCount === 1 ? "" : "s"}</small>
                  </Button>
                  {openConversation === item.claimId && (
                    <div className="conversation-log">
                      {item.messages.map((entry, index) => (
                        <div key={index} className={entry.role === "user" ? "log-user" : "log-assistant"}>
                          <span>{entry.role === "user" ? (claim?.employee?.name ?? "You") : "Assistant"}</span>
                          <p>{historyQuery.trim() ? highlight(entry.content, historyQuery.trim()) : entry.content}</p>
                        </div>
                      ))}
                      {item.status !== "SUBMITTED" && item.claimId !== claim?.id && (
                        <Button type="button" className="drawer-new" disabled={busy} onClick={() => { setHistoryOpen(false); void run(() => openClaim(item.claimId)); }}>
                          Continue this conversation
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              ))}
              {!conversations.length && <div className="drawer-empty">{historyQuery ? "No conversations mention that." : "No conversations yet."}</div>}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function highlight(text: string, query: string): ReactNode {
  const lower = text.toLowerCase();
  const needle = query.toLowerCase();
  const parts: ReactNode[] = [];
  let cursor = 0;
  let found = lower.indexOf(needle);
  while (found !== -1) {
    parts.push(text.slice(cursor, found), <mark key={found}>{text.slice(found, found + needle.length)}</mark>);
    cursor = found + needle.length;
    found = lower.indexOf(needle, cursor);
  }
  parts.push(text.slice(cursor));
  return parts;
}
