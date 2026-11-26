import { useState, useEffect, useRef, FormEvent, KeyboardEvent } from "react";
import { useParams, Link } from "react-router-dom";
import { documents, conversation, Document, Message } from "../api/client";

export default function ChatPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [doc, setDoc] = useState<Document | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!documentId) return;
    documents.get(documentId).then(setDoc).catch(() => {});
    conversation.history(documentId).then((c) => setMessages(c.messages)).catch(() => {});
  }, [documentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function handleSend(e?: FormEvent) {
    e?.preventDefault();
    if (!question.trim() || sending || !documentId) return;
    setError("");
    const q = question.trim();
    setQuestion("");
    setSending(true);

    // Optimistically add user message
    const tempUser: Message = {
      id: "temp-user",
      role: "user",
      content: q,
      citation_pages: [],
      citation_status: "n/a",
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUser]);

    try {
      const reply = await conversation.ask(documentId, q);
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== "temp-user"),
        // Re-fetch user message isn't returned; keep the optimistic one with server reply
        { ...tempUser, id: "user-" + reply.id },
        reply,
      ]);
    } catch (err: unknown) {
      setMessages((prev) => prev.filter((m) => m.id !== "temp-user"));
      setError(err instanceof Error ? err.message : "Failed to get an answer.");
    } finally {
      setSending(false);
    }
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function CitationBadges({ pages }: { pages: number[] }) {
    if (!pages.length) return null;
    return (
      <span style={styles.citations}>
        {pages.map((p) => (
          <span key={p} style={styles.citationBadge}>
            p.{p}
          </span>
        ))}
      </span>
    );
  }

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <Link to="/" style={styles.back}>
          ← Back
        </Link>
        <span style={styles.headerFilename}>{doc?.original_filename ?? "…"}</span>
        <span style={{ width: 60 }} />
      </header>

      <div style={styles.messages}>
        {messages.length === 0 && !sending && (
          <div style={styles.emptyState}>
            <p style={styles.emptyTitle}>Ask a question about this document</p>
            <p style={styles.emptyHint}>
              Every answer will include page citations so you can verify the source.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              ...styles.bubble,
              ...(msg.role === "user" ? styles.userBubble : styles.assistantBubble),
            }}
          >
            <p style={styles.bubbleText}>{msg.content}</p>
            {msg.role === "assistant" && <CitationBadges pages={msg.citation_pages} />}
          </div>
        ))}

        {sending && (
          <div style={{ ...styles.bubble, ...styles.assistantBubble }}>
            <p style={{ ...styles.bubbleText, color: "#9ca3af" }}>Thinking… (this may take up to 90 seconds)</p>
          </div>
        )}

        {error && <p style={styles.error}>{error}</p>}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} style={styles.inputArea}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          style={styles.textarea}
          disabled={sending}
          rows={2}
        />
        <button type="submit" disabled={sending || !question.trim()} style={styles.sendBtn}>
          Send
        </button>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { display: "flex", flexDirection: "column", height: "100vh", background: "#f9f9f9" },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 20px",
    background: "#fff",
    borderBottom: "1px solid #e5e5e5",
    flexShrink: 0,
  },
  back: { color: "#1a1a1a", textDecoration: "none", fontSize: 14, width: 60 },
  headerFilename: { fontWeight: 600, fontSize: 15, flex: 1, textAlign: "center", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  messages: { flex: 1, overflowY: "auto", padding: "24px 16px", maxWidth: 720, width: "100%", margin: "0 auto", boxSizing: "border-box" as const },
  emptyState: { textAlign: "center", marginTop: 80 },
  emptyTitle: { fontWeight: 600, fontSize: 18 },
  emptyHint: { color: "#9ca3af", fontSize: 14 },
  bubble: {
    maxWidth: "80%",
    padding: "12px 16px",
    borderRadius: 12,
    marginBottom: 12,
    wordBreak: "break-word",
  },
  userBubble: { background: "#1a1a1a", color: "#fff", marginLeft: "auto" },
  assistantBubble: { background: "#fff", border: "1px solid #e5e5e5" },
  bubbleText: { margin: 0, whiteSpace: "pre-wrap", lineHeight: 1.6 },
  citations: { display: "flex", gap: 4, flexWrap: "wrap", marginTop: 8 },
  citationBadge: {
    fontSize: 11,
    padding: "2px 7px",
    borderRadius: 4,
    background: "#f0f4ff",
    color: "#2563eb",
    fontWeight: 600,
  },
  error: { color: "#dc2626", fontSize: 13 },
  inputArea: {
    display: "flex",
    gap: 8,
    padding: "12px 16px",
    background: "#fff",
    borderTop: "1px solid #e5e5e5",
    maxWidth: 720,
    width: "100%",
    margin: "0 auto",
    boxSizing: "border-box" as const,
    flexShrink: 0,
  },
  textarea: {
    flex: 1,
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #ddd",
    fontSize: 14,
    resize: "none",
    fontFamily: "inherit",
    outline: "none",
  },
  sendBtn: {
    padding: "0 20px",
    background: "#1a1a1a",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    alignSelf: "flex-end",
    height: 42,
  },
};
