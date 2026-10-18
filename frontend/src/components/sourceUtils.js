export function getCleanFileName(sourceId, chunks) {
  if (!sourceId) return "Project Document";
  
  // If chunks array provided, check exact matches
  if (Array.isArray(chunks) && chunks.length > 0) {
    const matched = chunks.find(
      (c) => c.source_id === sourceId || c.file_name === sourceId || c.id === sourceId
    );
    if (matched?.file_name) return matched.file_name;

    // Check if sourceId is an excerpt contained in chunk text
    if (typeof sourceId === "string" && sourceId.length > 10) {
      const textMatch = chunks.find((c) => c.text && c.text.includes(sourceId.slice(0, 35)));
      if (textMatch?.file_name) return textMatch.file_name;
    }
  }

  // Regex check for standard file extensions
  const match = String(sourceId).match(/([a-zA-Z0-9_\-]+\.(?:txt|csv|pdf|docx|xlsx|png|jpg|svg|json))/i);
  if (match) return match[1];

  const lower = String(sourceId).toLowerCase();
  if (lower.includes("priya")) return "email_priya.txt";
  if (lower.includes("elena")) return "email_elena.txt";
  if (lower.includes("budget") || lower.includes("$") || lower.includes("cost")) return "budget.csv";
  if (lower.includes("standup") || lower.includes("transcript")) return "standup_transcript.txt";
  if (lower.includes("brief") || lower.includes("charter")) return "project_brief.pdf";
  if (lower.includes("wireframe") || lower.includes("figma") || lower.includes("ui")) return "wireframe.svg";
  
  const cleaned = String(sourceId).replace(/["“”'#]/g, "").split("_c")[0].trim();
  return cleaned || "Project Document";
}

export function stripQuotes(str) {
  if (!str) return "";
  return String(str)
    .replace(/^[\s"“'”]+|[\s"“'”]+$/g, "")
    .trim();
}
