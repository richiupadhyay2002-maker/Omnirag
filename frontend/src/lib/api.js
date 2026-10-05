const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Backend liveness probe (GET /health) used by the connection-status dot.
 * Rejects when the backend is unreachable or unhealthy.
 */
export async function health() {
  const r = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(4000) });
  if (!r.ok) throw new Error(`Unhealthy response (${r.status})`);
  return r.json();
}

export async function createWorkspace(name) {
  const r = await fetch(`${BASE_URL}/workspaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return r.json();
}

export async function uploadFile(wsId, file, onDone, onProgress) {
  const form = new FormData();
  form.append("file", file);

  // Default path (no progress callback): plain fetch, unchanged behavior.
  if (typeof onProgress !== "function") {
    const r = await fetch(`${BASE_URL}/workspaces/${wsId}/files`, { method: "POST", body: form });
    const data = await r.json();
    onDone?.(data);
    return data;
  }

  // Progress path: XHR, because fetch has no upload-progress events.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_URL}/workspaces/${wsId}/files`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON body (e.g. proxy error) — status below still decides */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100);
        onDone?.(data);
        resolve(data);
      } else {
        reject(new Error(data?.detail || `Upload failed (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed — is the backend running?"));
    xhr.send(form);
  });
}

export async function listFiles(wsId) {
  const r = await fetch(`${BASE_URL}/workspaces/${wsId}/files`);
  return r.json();
}

export async function deleteFile(fileId) {
  return fetch(`${BASE_URL}/files/${fileId}`, { method: "DELETE" });
}

export async function listConversations(wsId) {
  const r = await fetch(`${BASE_URL}/workspaces/${wsId}/conversations`);
  return r.json();
}

export async function createConversation(wsId) {
  const r = await fetch(`${BASE_URL}/workspaces/${wsId}/conversations`, { method: "POST" });
  return r.json();
}

export async function deleteConversation(convId) {
  return fetch(`${BASE_URL}/conversations/${convId}`, { method: "DELETE" });
}

export async function getMessages(convId) {
  const r = await fetch(`${BASE_URL}/conversations/${convId}/messages`);
  return r.json();
}

/**
 * Streams a chat response token-by-token using fetch + ReadableStream
 * (avoids EventSource's GET-only limitation since we need to POST a body).
 *
 * `fileIds` (optional) scopes retrieval to specific documents; omitted/empty
 * = search every file in the workspace (server default, unchanged).
 */
export async function streamChat({ workspaceId, conversationId, message, mode, fileIds }, onToken, onDone) {
  const body = { workspace_id: workspaceId, conversation_id: conversationId, message, mode };
  if (Array.isArray(fileIds) && fileIds.length > 0) body.file_ids = fileIds;

  const res = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`Chat request failed (${res.status})`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop();

    for (const evt of events) {
      const eventMatch = evt.match(/^event:\s*(.*)$/m);
      const dataMatch = evt.match(/^data:\s*(.*)$/m);
      const eventName = eventMatch?.[1] ?? "token";
      const data = dataMatch?.[1] ?? "";
      if (eventName === "token") onToken(data);
      if (eventName === "done") onDone?.(data);
    }
  }
}
