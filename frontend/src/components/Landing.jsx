import { Sparkles, FileText, Image as ImageIcon, Code2, Table2, FileType2 } from "lucide-react";
import UploadArea from "./UploadArea.jsx";

const FILE_TYPES = [
  { icon: FileText, label: "PDF" },
  { icon: FileType2, label: "DOCX / PPTX" },
  { icon: Code2, label: "Code" },
  { icon: Table2, label: "CSV / Excel" },
  { icon: ImageIcon, label: "Images" },
];

const EXAMPLES = [
  "Explain this chapter in simple language.",
  "Explain slide 15 and create a 5-mark exam answer.",
  "Does this code match the methodology in the paper?",
  "Which category has the highest value, and why?",
  "Compare these two research papers.",
];

export default function Landing({ onFilesSelected, onStartEmpty }) {
  return (
    <div className="relative min-h-screen bg-aurora-radial overflow-hidden flex flex-col items-center px-6">
      <div className="absolute -top-24 -left-24 w-96 h-96 bg-aurora-500/20 rounded-full blur-3xl animate-floatSlow" />
      <div className="absolute top-40 -right-24 w-96 h-96 bg-coral-500/10 rounded-full blur-3xl animate-floatSlow" />

      <div className="relative z-10 max-w-3xl w-full text-center pt-20 pb-10 animate-fadeUp">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-slate-300 mb-6">
          <Sparkles size={14} className="text-aurora-400" />
          Runs 100% locally · $0 to operate
        </div>
        <h1 className="font-display text-4xl sm:text-6xl font-bold text-white leading-tight">
          Ask Anything.
          <br />
          <span className="bg-clip-text text-transparent bg-aurora-line">From Any File.</span>
        </h1>
        <p className="mt-5 text-slate-400 text-lg max-w-xl mx-auto">
          OmniRAG turns your PDFs, slides, code, spreadsheets, and images into a
          knowledge base you can chat with — grounded, cited, and hallucination-checked.
        </p>
      </div>

      <div className="relative z-10 w-full max-w-2xl">
        <UploadArea onFilesSelected={onFilesSelected} large />
        <div className="flex justify-center gap-4 mt-4 flex-wrap">
          {FILE_TYPES.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-1.5 text-slate-400 text-xs bg-white/5 border border-white/10 rounded-full px-3 py-1.5">
              <Icon size={13} /> {label}
            </div>
          ))}
        </div>
      </div>

      <div className="relative z-10 max-w-2xl w-full mt-10 mb-16">
        <p className="text-slate-500 text-xs uppercase tracking-wider text-center mb-3">Try asking</p>
        <div className="grid sm:grid-cols-2 gap-2">
          {EXAMPLES.map((q) => (
            <div key={q} className="text-sm text-slate-300 bg-white/5 hover:bg-white/10 transition-colors border border-white/10 rounded-xl px-4 py-3 cursor-default">
              "{q}"
            </div>
          ))}
        </div>
        <button
          onClick={onStartEmpty}
          className="mt-6 mx-auto block text-sm text-slate-400 hover:text-white underline underline-offset-4 transition-colors"
        >
          Or start a new chat without uploading yet →
        </button>
      </div>
    </div>
  );
}
