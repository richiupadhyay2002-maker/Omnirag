import { useState } from "react";
import { ChevronDown, FileText, FileType2, Code2, Table2, Image as ImageIcon } from "lucide-react";

const ICONS = { pdf: FileText, docx: FileType2, pptx: FileType2, text: FileText, code: Code2, csv: Table2, image: ImageIcon };

export default function Citation({ citation, index }) {
  const [open, setOpen] = useState(false);
  const Icon = ICONS[citation.file_type] || FileText;

  return (
    <div className="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/[0.03] overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-white/[0.06] transition-colors"
      >
        <span className="text-[11px] font-semibold text-aurora-500 bg-aurora-500/10 rounded-full w-5 h-5 flex items-center justify-center shrink-0">
          {index}
        </span>
        <Icon size={14} className="text-slate-500 shrink-0" />
        <span className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate flex-1">
          {citation.filename}
        </span>
        <span className="text-[11px] text-slate-500 shrink-0">{citation.location}</span>
        <ChevronDown size={14} className={`text-slate-400 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 text-xs text-slate-600 dark:text-slate-400 border-t border-slate-200 dark:border-white/10 leading-relaxed">
          {citation.snippet}
          <div className="mt-1.5 text-[10px] text-slate-400 dark:text-slate-500">
            relevance score: {citation.score}
          </div>
        </div>
      )}
    </div>
  );
}
