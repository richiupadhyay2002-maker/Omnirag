import { useEffect, useRef, useState } from "react";
import { Send, Square, Trash2, Sparkles, ChevronDown, Plus, Loader2 } from "lucide-react";
import MessageBubble from "./MessageBubble.jsx";
import FileCard from "./FileCard.jsx";
import UploadArea from "./UploadArea.jsx";
import FileScopeSelector from "./FileScopeSelector.jsx";
import SuggestedQuestions from "./SuggestedQuestions.jsx";
import ConnectionStatus from "./ConnectionStatus.jsx";

const MODES = [
  { id: "default", label: "Default" },
  { id: "simple", label: "Explain Simply" },
  { id: "deep", label: "Deep Explanation" },
  { id: "exam", label: "Exam Answer" },
  { id: "code", label: "Code Explanation" },
  { id: "research", label: "Research Mode" },
];

export default function ChatWindow({
  files, onFilesSelected, onRemoveFile,
  messages, onSend, isStreaming, onStop, onClear,
  onRegenerate, canRegenerate,
}) {
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("default");
  const [modeOpen, setModeOpen] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [scopeIds, setScopeIds] = useState([]); // [] = All files (default scope)
  const scrollRef = useRef(null);

  const readyCount = files.filter((f) => f.status === "ready").length;
  const anyProcessing = files.some((f) => f.status === "processing");
  const blocked = files.length > 0 && readyCount === 0; // files exist, none usable yet
  const lastMessage = messages[messages.length - 1];
  const showFollowUps =
    messages.length > 0 &&
    !isStreaming &&
    lastMessage?.role === "assistant" &&
    !!lastMessage.content &&
    readyCount > 0;

  // Drop scope selections for files that were deleted or aren't ready anymore.
  useEffect(() => {
    setScopeIds((prev) =>
      prev.filter((id) => files.some((f) => f.file_id === id && f.status === "ready"))
    );
  }, [files]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const submit = (textOverride) => {
    const text = typeof textOverride === "string" ? textOverride.trim() : input.trim();
    if (!text || isStreaming || blocked) return;
    onSend(text, mode, scopeIds);
    if (typeof textOverride !== "string") setInput("");
  };

  return (
    <div className="flex-1 flex flex-col h-screen bg-white dark:bg-ink-950">
      {/* Top bar: files */}
      <div className="border-b border-slate-200 dark:border-white/10 px-6 py-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs uppercase tracking-wide text-slate-400 font-medium">
            Knowledge files ({files.length})
          </p>
          <div className="flex items-center gap-3">
            <ConnectionStatus />
            <button
              onClick={() => setShowUpload((s) => !s)}
              className="flex items-center gap-1 text-xs text-aurora-500 hover:text-aurora-400 font-medium"
            >
              <Plus size={13} /> Add files
            </button>
          </div>
        </div>
        {showUpload && (
          <div className="mb-3">
            <UploadArea onFilesSelected={onFilesSelected} onDone={() => setShowUpload(false)} />
          </div>
        )}
        {files.length > 0 ? (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {files.map((f) => (
              <div key={f.file_id} className="w-64 shrink-0">
                <FileCard file={f} onRemove={onRemoveFile} />
              </div>
            ))}
          </div>
        ) : (
          !showUpload && <p className="text-sm text-slate-400 py-1">No files uploaded to this workspace yet.</p>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-400 gap-3">
            <div className="w-14 h-14 rounded-2xl bg-aurora-500/10 flex items-center justify-center">
              <Sparkles className="text-aurora-500" size={26} />
            </div>
            <p className="font-medium text-slate-500 dark:text-slate-300">Ask a question about your files</p>
            <p className="text-sm max-w-sm">
              OmniRAG only answers from what you've uploaded, and always shows its sources.
            </p>
            {readyCount > 0 && (
              <div className="mt-2">
                <SuggestedQuestions variant="starter" onPick={submit} />
              </div>
            )}
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble
            key={i}
            message={m}
            isStreaming={isStreaming && i === messages.length - 1 && m.role === "assistant"}
            onRegenerate={
              canRegenerate && !isStreaming && m.role === "assistant" && i === messages.length - 1 && m.content
                ? onRegenerate
                : undefined
            }
          />
        ))}
        {showFollowUps && (
          <div className="pl-11">
            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-medium mb-2">Keep going</p>
            <SuggestedQuestions variant="followup" limit={3} onPick={submit} />
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-slate-200 dark:border-white/10 p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="relative">
            <button
              onClick={() => setModeOpen((o) => !o)}
              className="flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 rounded-full px-3 py-1.5 transition-colors"
            >
              {MODES.find((m) => m.id === mode)?.label} <ChevronDown size={13} />
            </button>
            {modeOpen && (
              <div className="absolute bottom-full mb-2 left-0 bg-white dark:bg-ink-800 border border-slate-200 dark:border-white/10 rounded-xl shadow-soft overflow-hidden z-10 min-w-[180px]">
                {MODES.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => { setMode(m.id); setModeOpen(false); }}
                    className={`w-full text-left text-sm px-3 py-2 hover:bg-slate-100 dark:hover:bg-white/10 ${mode === m.id ? "text-aurora-500 font-medium" : "text-slate-600 dark:text-slate-300"}`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {messages.length > 0 && (
            <button onClick={onClear} className="flex items-center gap-1 text-xs text-slate-400 hover:text-coral-500 ml-auto">
              <Trash2 size={13} /> Clear conversation
            </button>
          )}
        </div>

        <FileScopeSelector files={files} selectedIds={scopeIds} onChange={setScopeIds} />
        {blocked && (
          <p className="flex items-center gap-1.5 text-xs text-aurora-400 mb-2">
            <Loader2 size={12} className="animate-spin" />
            Still indexing your files — you can ask as soon as one is ready.
          </p>
        )}
        {!blocked && anyProcessing && (
          <p className="text-xs text-slate-400 mb-2">
            Some files are still indexing — answers use the ready ones.
          </p>
        )}

        <div className="flex items-end gap-2 rounded-2xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/[0.04] px-3 py-2 focus-within:ring-2 focus-within:ring-aurora-400/40">
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder={blocked ? "Waiting for files to finish indexing…" : "Ask anything about your uploaded files…"}
            className="flex-1 resize-none bg-transparent outline-none text-[15px] py-2 max-h-40 dark:text-white placeholder:text-slate-400"
          />
          {isStreaming ? (
            <button onClick={onStop} className="shrink-0 w-9 h-9 rounded-xl bg-coral-500 hover:bg-coral-400 text-white flex items-center justify-center transition-colors">
              <Square size={15} />
            </button>
          ) : (
            <button
              onClick={() => submit()}
              disabled={!input.trim() || blocked}
              className="shrink-0 w-9 h-9 rounded-xl bg-aurora-600 hover:bg-aurora-500 disabled:opacity-40 disabled:hover:bg-aurora-600 text-white flex items-center justify-center transition-colors"
            >
              <Send size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
