import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, RotateCcw, Check, Sparkles, User } from "lucide-react";
import { useState } from "react";
import Citation from "./Citation.jsx";

function CodeBlock({ className, children }) {
  const [copied, setCopied] = useState(false);
  const lang = /language-(\w+)/.exec(className || "")?.[1] || "text";
  const code = String(children).replace(/\n$/, "");

  return (
    <div className="relative group my-2">
      <button
        onClick={() => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-white/10 hover:bg-white/20 rounded-lg p-1.5 text-slate-300"
      >
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </button>
      <SyntaxHighlighter language={lang} style={oneDark} customStyle={{ borderRadius: "0.75rem", fontSize: "0.85rem" }}>
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

export default function MessageBubble({ message, onRegenerate, isStreaming }) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const copyMessage = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (isUser) {
    return (
      <div className="flex justify-end gap-3 animate-fadeUp">
        <div className="max-w-2xl bg-aurora-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-[15px] leading-relaxed">
          {message.content}
        </div>
        <div className="w-8 h-8 rounded-full bg-ink-800 dark:bg-white/10 flex items-center justify-center shrink-0">
          <User size={16} className="text-slate-300" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 animate-fadeUp">
      <div className="w-8 h-8 rounded-full bg-aurora-line flex items-center justify-center shrink-0">
        <Sparkles size={15} className="text-white" />
      </div>
      <div className="max-w-2xl flex-1">
        <div className="rounded-2xl rounded-tl-sm bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 px-4 py-3 text-[15px] leading-relaxed">
          <div className="prose-omni prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ code: ({ className, children }) => <CodeBlock className={className}>{children}</CodeBlock> }}
            >
              {message.content || (isStreaming ? "" : "")}
            </ReactMarkdown>
            {isStreaming && <span className="inline-block w-1.5 h-4 bg-aurora-400 ml-0.5 animate-pulseDot align-middle" />}
          </div>
        </div>

        {message.citations?.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-medium">Sources</p>
            {message.citations.map((c, i) => <Citation key={i} citation={c} index={i + 1} />)}
          </div>
        )}

        {!isStreaming && message.content && (
          <div className="flex items-center gap-1 mt-1.5">
            <button onClick={copyMessage} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors">
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
            {onRegenerate && (
              <button onClick={onRegenerate} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors">
                <RotateCcw size={14} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
