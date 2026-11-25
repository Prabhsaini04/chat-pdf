import { useState, useEffect, useRef, ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { documents, auth, Document } from "../api/client";

interface Props {
  onLogout: () => void;
}

export default function DocumentsPage({ onLogout }: Props) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDocs();
    // Poll while any doc is processing
    const id = setInterval(() => {
      setDocs((prev) => {
        if (prev.some((d) => d.status === "processing")) loadDocs();
        return prev;
      });
    }, 3000);
    return () => clearInterval(id);
  }, []);

  async function loadDocs() {
    try {
      setDocs(await documents.list());
    } catch {
      /* ignore polling errors */
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      await documents.upload(file);
      await loadDocs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Move this document to trash? You can restore it within 30 days.")) return;
    try {
      await documents.delete(id);
      await loadDocs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  async function handleLogout() {
    await auth.logout().catch(() => {});
    onLogout();
  }

  function statusBadge(status: Document["status"]) {
    const map: Record<string, { label: string; color: string }> = {
      ready: { label: "Ready", color: "#16a34a" },
      processing: { label: "Processing…", color: "#d97706" },
      uploading: { label: "Uploading…", color: "#2563eb" },
      failed: { label: "Failed", color: "#dc2626" },
      soft_deleted: { label: "Deleted", color: "#9ca3af" },
    };
    const s = map[status] ?? { label: status, color: "#666" };
    return (
      <span style={{ color: s.color, fontWeight: 600, fontSize: 12 }}>
        {s.label}
      </span>
    );
  }

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h2 style={styles.headerTitle}>📄 chat-pdf</h2>
        <button onClick={handleLogout} style={styles.linkBtn}>
          Sign out
        </button>
      </header>

      <div style={styles.container}>
        <div style={styles.row}>
          <h1 style={styles.title}>My Documents</h1>
          <label style={styles.uploadBtn}>
            {uploading ? "Uploading…" : "Upload PDF"}
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleUpload}
              disabled={uploading}
              style={{ display: "none" }}
            />
          </label>
        </div>

        {error && <p style={styles.error}>{error}</p>}

        {loading ? (
          <p style={styles.muted}>Loading…</p>
        ) : docs.length === 0 ? (
          <div style={styles.empty}>
            <p>No documents yet.</p>
            <p style={styles.muted}>Upload a PDF to get started.</p>
          </div>
        ) : (
          <ul style={styles.list}>
            {docs.map((doc) => (
              <li key={doc.id} style={styles.item}>
                <div style={styles.itemMain}>
                  <span style={styles.filename}>{doc.original_filename}</span>
                  <div style={styles.meta}>
                    {statusBadge(doc.status)}
                    {doc.page_count != null && (
                      <span style={styles.muted}>{doc.page_count} pages</span>
                    )}
                    <span style={styles.muted}>
                      {(doc.size_bytes / 1024).toFixed(0)} KB
                    </span>
                  </div>
                  {doc.status === "failed" && doc.failure_reason && (
                    <p style={styles.failureReason}>{doc.failure_reason}</p>
                  )}
                </div>
                <div style={styles.itemActions}>
                  {doc.status === "ready" && (
                    <Link to={`/documents/${doc.id}`} style={styles.chatBtn}>
                      Chat
                    </Link>
                  )}
                  <button
                    onClick={() => handleDelete(doc.id)}
                    style={styles.deleteBtn}
                    disabled={doc.status === "soft_deleted"}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#f9f9f9" },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 24px",
    background: "#fff",
    borderBottom: "1px solid #e5e5e5",
  },
  headerTitle: { margin: 0, fontSize: 18, fontWeight: 700 },
  linkBtn: {
    background: "none",
    border: "none",
    color: "#666",
    cursor: "pointer",
    fontSize: 14,
  },
  container: { maxWidth: 720, margin: "0 auto", padding: "32px 16px" },
  row: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 },
  title: { margin: 0, fontSize: 24, fontWeight: 700 },
  uploadBtn: {
    padding: "10px 20px",
    background: "#1a1a1a",
    color: "#fff",
    borderRadius: 8,
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
  },
  error: { color: "#dc2626", fontSize: 13, marginBottom: 16 },
  empty: { textAlign: "center", padding: "48px 0" },
  muted: { color: "#9ca3af", fontSize: 13, margin: 0 },
  list: { listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12 },
  item: {
    background: "#fff",
    border: "1px solid #e5e5e5",
    borderRadius: 10,
    padding: "16px 20px",
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
  },
  itemMain: { flex: 1, minWidth: 0 },
  filename: { fontWeight: 600, fontSize: 15, display: "block", wordBreak: "break-word" },
  meta: { display: "flex", gap: 12, marginTop: 4, alignItems: "center" },
  failureReason: { color: "#dc2626", fontSize: 12, marginTop: 4, marginBottom: 0 },
  itemActions: { display: "flex", gap: 8, flexShrink: 0 },
  chatBtn: {
    padding: "7px 16px",
    background: "#1a1a1a",
    color: "#fff",
    borderRadius: 7,
    textDecoration: "none",
    fontSize: 13,
    fontWeight: 600,
  },
  deleteBtn: {
    padding: "7px 14px",
    background: "none",
    border: "1px solid #e5e5e5",
    borderRadius: 7,
    cursor: "pointer",
    fontSize: 13,
    color: "#666",
  },
};
