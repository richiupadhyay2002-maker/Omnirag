import { FileText, FileType2, Code2, Table2, Image as ImageIcon, X, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

const ICONS = {
  pdf: FileText,
  docx: FileType2,
  pptx: FileType2,
  text: FileText,
  code: Code2,
  csv: Table2,
  image: ImageIcon,
};

const COLORS = {
  pdf: "text-coral-400 bg-coral-500/10",
  docx: "text-aurora-400 bg-aurora-500/10",
  pptx: "text-aurora-400 bg-aurora-500/10",
  text: "text-slate-300 bg-white/10",
  code: "text-mint-400 bg-mint-500/10",
  csv: "text-mint-400 bg-mint-500/10",
  image: "text-coral-400 bg-coral-500/10",
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileCard({ file, onRemove }) {
  const Icon = ICONS[file.file_type] || FileText;
  const colorClass = COLORS[file.file_type] || "text-slate-300 bg-white/10";

  return (
    <div className="group relative flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.07] px-3.5 py-3 transition-colors animate-fadeUp">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${colorClass}`}>
        <Icon size={18} />
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-white truncate" title={file.filename}>
          {file.filename}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-slate-500 uppercase">{file.file_type}</span>
          <span className="text-xs text-slate-600">·</span>
          <span className="text-xs text-slate-500">{formatSize(file.size_bytes)}</span>
          {file.status === "ready" && file.num_chunks > 0 && (
            <>
              <span className="text-xs text-slate-600">·</span>
              <span className="text-xs text-slate-500">{file.num_chunks} chunks</span>
            </>
          )}
        </div>
      </div>

      <div className="shrink-0">
        {file.status === "processing" && <Loader2 size={16} className="text-aurora-400 animate-spin" />}
        {file.status === "ready" && <CheckCircle2 size={16} className="text-mint-400" />}
        {file.status === "error" && (
          <span title={file.error_message}>
            <AlertCircle size={16} className="text-coral-500" />
          </span>
        )}
      </div>

      <button
        onClick={() => onRemove(file.file_id)}
        className="opacity-0 group-hover:opacity-100 transition-opacity absolute -top-2 -right-2 w-6 h-6 rounded-full bg-ink-800 border border-white/10 flex items-center justify-center text-slate-400 hover:text-white hover:border-white/30"
        title="Remove file"
      >
        <X size={12} />
      </button>
    </div>
  );
}
