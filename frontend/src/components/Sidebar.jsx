import { Plus, MessageSquare, Trash2, Pencil, Sun, Moon, Sparkles } from "lucide-react";
import { useState } from "react";

export default function Sidebar({ conversations, activeId, onSelect, onNew, onDelete, onRename, dark, onToggleDark }) {
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");

  const startEdit = (c) => { setEditingId(c.conversation_id || c.id); setEditValue(c.title); };
  const commitEdit = (id) => { onRename(id, editValue.trim() || "Untitled"); setEditingId(null); };

  return (
    <aside className="w-72 shrink-0 h-screen flex flex-col bg-slate-50 dark:bg-ink-900 border-r border-slate-200 dark:border-white/10">
      <div className="p-4 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-aurora-line flex items-center justify-center">
          <Sparkles size={16} className="text-white" />
        </div>
        <span className="font-display font-bold text-lg dark:text-white">OmniRAG</span>
      </div>

      <div className="px-3">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 justify-center rounded-xl bg-aurora-600 hover:bg-aurora-500 text-white text-sm font-medium py-2.5 transition-colors shadow-glow"
        >
          <Plus size={16} /> New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 mt-4 space-y-1">
        <p className="text-[11px] uppercase tracking-wide text-slate-400 px-2 mb-1.5">Conversations</p>
        {conversations.length === 0 && (
          <p className="text-sm text-slate-400 px-2 py-6 text-center">No conversations yet</p>
        )}
        {conversations.map((c) => {
          const id = c.conversation_id || c.id;
          const isActive = id === activeId;
          return (
            <div
              key={id}
              onClick={() => onSelect(id)}
              className={`group flex items-center gap-2 rounded-xl px-3 py-2.5 cursor-pointer text-sm transition-colors ${
                isActive ? "bg-aurora-500/15 text-aurora-600 dark:text-aurora-300" : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
              }`}
            >
              <MessageSquare size={15} className="shrink-0" />
              {editingId === id ? (
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={() => commitEdit(id)}
                  onKeyDown={(e) => e.key === "Enter" && commitEdit(id)}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 bg-transparent border-b border-aurora-400 outline-none text-sm"
                />
              ) : (
                <span className="flex-1 truncate">{c.title}</span>
              )}
              <div className="hidden group-hover:flex items-center gap-1 shrink-0">
                <button onClick={(e) => { e.stopPropagation(); startEdit(c); }} className="p-1 hover:text-aurora-500">
                  <Pencil size={13} />
                </button>
                <button onClick={(e) => { e.stopPropagation(); onDelete(id); }} className="p-1 hover:text-coral-500">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="p-3 border-t border-slate-200 dark:border-white/10">
        <button
          onClick={onToggleDark}
          className="w-full flex items-center gap-2 justify-center rounded-xl text-sm py-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors"
        >
          {dark ? <Sun size={15} /> : <Moon size={15} />}
          {dark ? "Light mode" : "Dark mode"}
        </button>
      </div>
    </aside>
  );
}
