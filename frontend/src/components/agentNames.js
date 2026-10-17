const AGENT_FRIENDLY_NAMES = {
  text_agent: "Requirements Analyst",
  budget_agent: "Finance & Budget Specialist",
  risk_agent: "Compliance & Risk Auditor",
  ops_agent: "Operations & Action Planner",
  vision_agent: "UI & Wireframe Specialist",
  document_agent: "Document & Data Parser",
  validator_agent: "Consensus Validator",
  diagram_agent: "Architecture Specialist",
};

export function formatAgentName(name) {
  if (!name) return "Agent not reported";
  return AGENT_FRIENDLY_NAMES[name] || name.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
