import clsx from "clsx";
import { Sparkles } from "lucide-react";

const STARTERS = [
  "Summarize this document",
  "What are the key findings?",
  "List the main takeaways",
  "Explain the important concepts simply",
];

const FOLLOW_UPS = [
  "Can you go deeper on the main points?",
  "What evidence supports the conclusions?",
  "Give me a quick recap with sources",
];

/**
 * Clickable question chips — starter prompts on the empty state, follow-up
 * prompts after an answer. Static templates (no backend round-trip).
 */
export default function SuggestedQuestions({ variant = "starter", onPick, limit = 4 }) {
  const list = (variant === "followup" ? FOLLOW_UPS : STARTERS).slice(0, limit);

  return (
    <div className={clsx("flex flex-wrap gap-2", variant === "starter" && "justify-center")}>
      {list.map((q) => (
        <button
          key={q}
          onClick={() => onPick(q)}
          className={clsx(
            "rounded-full border px-3.5 py-2 text-xs sm:text-sm transition-colors",
            "border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.04]",
            "text-slate-600 dark:text-slate-300",
            "hover:border-aurora-400/50 hover:text-aurora-500 dark:hover:text-aurora-400 hover:bg-aurora-500/5"
          )}
        >
          {q}
        </button>
      ))}
    </div>
  );
}