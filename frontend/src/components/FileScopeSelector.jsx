import clsx from "clsx";
import { Files, FileText } from "lucide-react";

/**
 * Per-document chat scope: checkbox chips rendered above the composer.
 *
 * `selectedIds` = [] means "All files" (default). Clicking a file chip while
 * "All files" is active narrows the scope to just that file; deselecting the
 * last file falls back to "All files".
 */
export default function FileScopeSelector({ files, selectedIds, onChange }) {
  const ready = files.filter((f) => f.status === "ready");
  if (ready.length < 2) return null; // scoping needs a choice to be meaningful

  const allSelected = selectedIds.length === 0;

  const toggleFile = (id) => {
    if (allSelected) {
      onChange([id]); // narrow from "All files" to a single document
    } else if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id)); // empty list falls back to all
    } else {
      onChange([...selectedIds, id]);
    }
  };

  const chipCls = (active) =>
    clsx(
      "flex items-center gap-1.5 shrink-0 rounded-full px-3 py-1.5 text-xs border transition-colors",
      active
        ? "bg-aurora-500/15 border-aurora-400/40 text-aurora-500 dark:text-aurora-400 font-medium"
        : "bg-slate-100 dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-white/25 hover:text-slate-700 dark:hover:text-slate-200"
    );

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-2 -mx-1 px-1">
      <span className="text-[11px] uppercase tracking-wide text-slate-400 font-medium shrink-0">
        Ask about
      </span>
      <button onClick={() => onChange([])} className={chipCls(allSelected)} title="Search every ready file">
        <Files size={12} /> All files
      </button>
      {ready.map((f) => (
        <button
          key={f.file_id}
          onClick={() => toggleFile(f.file_id)}
          className={chipCls(!allSelected && selectedIds.includes(f.file_id))}
          title={`Search only ${f.filename}`}
        >
          <FileText size={12} />
          <span className="max-w-[140px] truncate">{f.filename}</span>
        </button>
      ))}
    </div>
  );
}