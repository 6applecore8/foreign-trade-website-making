// Multipart submission to the intake server.
// Contract: exactly one "payload" text part plus one part per reference
// ("reference:<client_id>") and an optional "seo_file" part.

export async function submitRequest(payload, references, seoFile) {
  const data = new FormData();
  data.append("payload", JSON.stringify(payload));
  references.forEach((ref) => {
    if (ref.file) data.append("reference:" + ref.client_id, ref.file, ref.file.name);
  });
  if (seoFile) data.append("seo_file", seoFile, seoFile.name);
  const response = await fetch("/api/requests", { method: "POST", body: data });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.message || result.error || "保存失败");
  }
  return result;
}

export async function startAgent(requestId) {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId })
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.message || result.error || "Agent 启动失败");
  }
  return result;
}

export async function getAgentRun(runId) {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || result.error || "无法读取 Agent 状态");
  return result;
}
