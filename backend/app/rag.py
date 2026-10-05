"""
Core RAG orchestration. Retrieves relevant chunks across all uploaded files in
a workspace, builds a grounded prompt (with an explicit "not found" instruction
to prevent hallucination), and streams the generation while separately
returning structured citations for the UI's source cards.
"""
from typing import Iterator
from app import vectorstore, memory
from app.llm import generate_stream

MODE_INSTRUCTIONS = {
    "default": "Answer clearly and directly using only the provided context.",
    "simple": "Explain the answer in very simple, plain language as if teaching a beginner. Avoid jargon.",
    "deep": "Give a thorough, technical, in-depth explanation, including nuances and edge cases found in the context.",
    "exam": "Write the answer in the style of a well-structured exam answer worth the marks implied by the question, "
            "with headings, key points, and a concise conclusion.",
    "code": "Focus on explaining code behavior, structure, functions, and logic precisely, referencing exact "
            "functions/line ranges from the context.",
    "research": "Adopt a research-analysis tone: compare claims across sources, note agreements/contradictions, "
                "and cite methodology details precisely.",
}

SYSTEM_PROMPT = """You are OmniRAG, an assistant that answers questions strictly using the CONTEXT
provided from the user's uploaded files. Rules:

1. Only use information present in the CONTEXT below. Do not use outside/general knowledge to state facts
   about the files' content.
2. If the answer is not present in the CONTEXT, clearly say: "I couldn't find this in the uploaded files."
   Do not invent or guess.
3. When you use information from the context, be precise about which file and location it came from
   (this is shown separately as citations, but stay faithful to the source).
4. When multiple files are involved, distinguish clearly which source supports which part of your answer.
5. Format your answer in clean Markdown: use headings, bullet points, tables, and fenced code blocks
   (with language tags) where appropriate.
"""


def _build_context_block(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, start=1):
        blocks.append(
            f"[Source {i}: {h['filename']} — {h['location']}]\n{h['text']}"
        )
    return "\n\n---\n\n".join(blocks)


def _hits_to_citations(hits: list[dict]) -> list[dict]:
    return [{
        "file_id": h["file_id"],
        "filename": h["filename"],
        "file_type": h["file_type"],
        "location": h["location"],
        "snippet": h["text"][:280] + ("..." if len(h["text"]) > 280 else ""),
        "score": h["score"],
    } for h in hits]


def answer_question(
    workspace_id: str,
    question: str,
    mode: str = "default",
    file_ids: list[str] | None = None,
    top_k: int = 8,
) -> tuple[Iterator[str], list[dict]]:
    """
    Returns (token_stream, citations). Citations are computed up-front (retrieval
    is not streamed), the token_stream yields the generated answer text.
    """
    hits = vectorstore.query(workspace_id, question, top_k=top_k, file_ids=file_ids)

    if not hits:
        def empty_stream():
            yield ("I couldn't find any relevant information in the uploaded files for this question. "
                   "Try uploading a file or rephrasing your question.")
        return empty_stream(), []

    context_block = _build_context_block(hits)
    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["default"])

    user_prompt = f"""MODE INSTRUCTION: {mode_instruction}

CONTEXT:
{context_block}

QUESTION:
{question}
"""

    # If any retrieved chunk is an image with no useful OCR text, pass its image
    # to the vision model so diagrams/screenshots can be genuinely "seen".
    image_paths = [h["image_path"] for h in hits if h.get("image_path")]

    stream = generate_stream(SYSTEM_PROMPT, user_prompt, image_paths=image_paths or None)
    citations = _hits_to_citations(hits)
    return stream, citations


def run_chat(workspace_id: str, conversation_id: str, question: str, mode: str, file_ids: list[str] | None = None):
    """Persists the user message, runs RAG, streams tokens, then persists the
    full assistant answer + citations once streaming completes."""
    memory.add_message(conversation_id, "user", question)
    stream, citations = answer_question(workspace_id, question, mode=mode, file_ids=file_ids)

    full_answer = []
    for token in stream:
        full_answer.append(token)
        yield token

    memory.add_message(conversation_id, "assistant", "".join(full_answer), citations)
