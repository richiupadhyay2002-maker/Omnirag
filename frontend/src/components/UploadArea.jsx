import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import clsx from "clsx";

export default function UploadArea({ onFilesSelected, onDone, large = false }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  // Per-file upload progress: [{ name, pct }] — cleared once every file hits 100%.
  const [uploads, setUploads] = useState([]);
  const doneRef = useRef(new Set());

  const handleFiles = (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    doneRef.current = new Set();
    setUploads(files.map((f) => ({ name: f.name, pct: 0 })));

    const onProgress = (index, pct) => {
      setUploads((prev) => prev.map((u, i) => (i === index ? { ...u, pct } : u)));
      if (pct >= 100) {
        doneRef.current.add(index);
        if (doneRef.current.size === files.length) {
          // Brief beat at 100% so the user sees completion, then hand off.
          window.setTimeout(() => {
            setUploads([]);
            onDone?.();
          }, 600);
        }
      }
    };

    onFilesSelected(files, onProgress);
  };

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "cursor-pointer rounded-3xl border-2 border-dashed transition-all duration-200 flex flex-col items-center justify-center text-center",
          large ? "py-16 px-8" : "py-8 px-6",
          dragging
            ? "border-aurora-400 bg-aurora-500/10 shadow-glow scale-[1.01]"
            : "border-white/15 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/25"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <div className="w-14 h-14 rounded-2xl bg-aurora-500/15 flex items-center justify-center mb-4">
          <UploadCloud className="text-aurora-400" size={28} />
        </div>
        <p className="text-white font-medium">
          {dragging ? "Drop your files here" : "Drag & drop files, or click to browse"}
        </p>
        <p className="text-slate-500 text-sm mt-1">
          PDF, DOCX, PPTX, TXT, code, CSV/Excel, images — up to 100MB each
        </p>
      </div>

      {uploads.length > 0 && (
        <div className="mt-3 space-y-2">
          {uploads.map((u, i) => (
            <div key={`${u.name}-${i}`} className="rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-2.5">
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <p className="text-xs text-slate-300 truncate">{u.name}</p>
                <span className="text-xs text-slate-500 shrink-0">{u.pct}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full bg-aurora-line transition-all duration-200"
                  style={{ width: `${u.pct}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
