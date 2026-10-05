import { useEffect, useState, useCallback, useRef } from "react";
import Landing from "./components/Landing.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import * as api from "./lib/api.js";

const WORKSPACE_KEY = "omnirag_workspace_id";

export default function App() {
  const [dark, setDark] = useState(true);
  const [started, setStarted] = useState(false);
  const [workspaceId, setWorkspaceId] = useState(null);
  const [files, setFiles] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [lastRequest, setLastRequest] = useState(null); // last sent prompt (for regenerate)
  const stopRef = useRef(false);
  // Shareable deep link: ?w=<workspace>&c=<conversation>, read once on load.
  const [deepLink] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    return { ws: p.get("w"), conv: p.get("c") };
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  // Bootstrap: URL (?w=) > localStorage > create a new workspace lazily
  const ensureWorkspace = useCallback(async (urlWs) => {
    let id = urlWs || new URLSearchParams(window.location.search).get("w") || localStorage.getItem(WORKSPACE_KEY);
    if (!id) {
      const ws = await api.createWorkspace("My Workspace");
      id = ws.id;
    }
    localStorage.setItem(WORKSPACE_KEY, id); // also adopts a shared ?w= workspace
    setWorkspaceId(id);
    return id;
  }, []);

  useEffect(() => {
    const init = async () => {
      try {
        const id = await ensureWorkspace(deepLink.ws);
        const convs = await api.listConversations(id);
        setConversations(convs);
        await refreshFiles(id);
        // Deep link: open the shared conversation if it lives in this workspace
        if (deepLink.conv && convs.some((c) => (c.conversation_id || c.id) === deepLink.conv)) {
          setActiveConvId(deepLink.conv);
          const msgs = await api.getMessages(deepLink.conv);
          setMessages(msgs.map((m) => ({ role: m.role, content: m.content, citations: m.citations })));
        }
      } catch (err) {
        console.error("Init failed (is the backend running?):", err);
      }
      // Shared links land directly in the chat view
      if (deepLink.ws || deepLink.conv) setStarted(true);
    };
    init();
  }, []);

  const refreshFiles = async (wsId) => {
    const data = await api.listFiles(wsId || workspaceId);
    setFiles(data);
  };

  const refreshConversations = async (wsId) => {
    const data = await api.listConversations(wsId || workspaceId);
    setConversations(data);
  };

  // Poll file processing status while anything is "processing"
  useEffect(() => {
    if (!workspaceId) return;
    const anyProcessing = files.some((f) => f.status === "processing");
    if (!anyProcessing) return;
    const t = setInterval(() => refreshFiles(workspaceId), 2000);
    return () => clearInterval(t);
  }, [files, workspaceId]);

  // Keep ?w=…&c=… in the URL so the current chat is a shareable link.
  useEffect(() => {
    if (!workspaceId) return;
    const params = new URLSearchParams(window.location.search);
    params.set("w", workspaceId);
    if (activeConvId) params.set("c", activeConvId);
    else params.delete("c");
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }, [workspaceId, activeConvId]);

  const handleFilesSelected = async (fileList, onProgress) => {
    let wsId = null;
    try {
      wsId = await ensureWorkspace();
    } catch (err) {
      console.error("Upload aborted — backend unreachable:", err);
    }
    if (!wsId) {
      // Clear any progress UI so the upload panel doesn't hang at 0%.
      fileList.forEach((_, i) => onProgress?.(i, 100));
      return;
    }
    let index = 0;
    for (const file of fileList) {
      try {
        await api.uploadFile(wsId, file, undefined, onProgress ? (pct) => onProgress(index, pct) : undefined);
      } catch (err) {
        console.error(`Upload failed for ${file.name}:`, err);
        onProgress?.(index, 100); // don't stall the progress UI on a failed file
      }
      index += 1;
    }
    await refreshFiles(wsId).catch(() => {});
    if (!started) {
      // First-run (landing) flow: let the bars hit 100% before entering the chat.
      await new Promise((r) => setTimeout(r, 350));
      setStarted(true);
    }
  };

  const handleRemoveFile = async (fileId) => {
    await api.deleteFile(fileId);
    setFiles((prev) => prev.filter((f) => f.file_id !== fileId));
  };

  const handleStartEmpty = () => setStarted(true);

  const selectConversation = async (id) => {
    setActiveConvId(id);
    setLastRequest(null); // regenerate only applies to the current session's prompt
    const msgs = await api.getMessages(id);
    setMessages(msgs.map((m) => ({ role: m.role, content: m.content, citations: m.citations })));
  };

  const newConversation = async () => {
    const conv = await api.createConversation(workspaceId);
    setConversations((prev) => [conv, ...prev]);
    setActiveConvId(conv.id);
    setLastRequest(null);
    setMessages([]);
  };

  const deleteConv = async (id) => {
    await api.deleteConversation(id);
    setConversations((prev) => prev.filter((c) => (c.conversation_id || c.id) !== id));
    if (activeConvId === id) { setActiveConvId(null); setMessages([]); }
  };

  const renameConv = async (id, title) => {
    setConversations((prev) => prev.map((c) => (c.conversation_id || c.id) === id ? { ...c, title } : c));
    await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/conversations/${id}?title=${encodeURIComponent(title)}`, { method: "PATCH" });
  };

  const clearConversation = () => setMessages([]);

  const sendMessage = async (text, mode, fileIds) => {
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "", citations: [] }]);
    setIsStreaming(true);
    stopRef.current = false;
    setLastRequest({ text, mode, fileIds });

    let convId = activeConvId;

    try {
      await api.streamChat(
        { workspaceId, conversationId: convId, message: text, mode, fileIds },
        (token) => {
          if (stopRef.current) return;
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { ...copy[copy.length - 1], content: copy[copy.length - 1].content + token };
            return copy;
          });
        },
        (finalConvId) => {
          if (!activeConvId) {
            setActiveConvId(finalConvId);
            refreshConversations(workspaceId);
          } else {
            refreshConversations(workspaceId);
          }
        }
      );
    } catch (err) {
      console.error("Chat request failed:", err);
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last?.role === "assistant") {
          copy[copy.length - 1] = {
            ...last,
            content:
              "Couldn't reach the backend. Make sure `uvicorn app.main:app --reload --port 8000` is running, then hit regenerate to try again.",
          };
        }
        return copy;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  // Re-asks the last prompt, replacing the last user + assistant pair in the UI.
  const regenerateLast = async () => {
    if (!lastRequest || isStreaming) return;
    setMessages((prev) => prev.slice(0, -2));
    await sendMessage(lastRequest.text, lastRequest.mode, lastRequest.fileIds);
  };

  const stopGeneration = () => {
    stopRef.current = true;
    setIsStreaming(false);
  };

  if (!started) {
    return <Landing onFilesSelected={handleFilesSelected} onStartEmpty={handleStartEmpty} />;
  }

  return (
    <div className="flex h-screen">
      <Sidebar
        conversations={conversations}
        activeId={activeConvId}
        onSelect={selectConversation}
        onNew={newConversation}
        onDelete={deleteConv}
        onRename={renameConv}
        dark={dark}
        onToggleDark={() => setDark((d) => !d)}
      />
      <ChatWindow
        files={files}
        onFilesSelected={handleFilesSelected}
        onRemoveFile={handleRemoveFile}
        messages={messages}
        onSend={sendMessage}
        isStreaming={isStreaming}
        onStop={stopGeneration}
        onClear={clearConversation}
        onRegenerate={regenerateLast}
        canRegenerate={!!lastRequest}
      />
    </div>
  );
}
