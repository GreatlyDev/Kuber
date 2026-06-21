const approvalList = document.querySelector("#approval-list");
const queueStatus = document.querySelector("#queue-status");
const refreshButton = document.querySelector("#refresh-button");
const approvedByInput = document.querySelector("#approved-by");

async function readJsonResponse(response) {
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = typeof body.detail === "string" ? body.detail : response.statusText;
    throw new Error(message);
  }

  return body;
}

async function requestJson(url, options = {}) {
  return readJsonResponse(await fetch(url, options));
}

function setQueueStatus(message) {
  queueStatus.textContent = message;
}

function createTextElement(tagName, className, text) {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  return element;
}

function formatPlanTitle(plan) {
  const action = plan.intent.action;
  const app = plan.intent.app;
  const namespace = plan.intent.namespace;
  return `${action} ${app} in ${namespace}`;
}

function formatPlanDetails(plan) {
  if (plan.intent.image) {
    return `Image ${plan.intent.image}`;
  }
  if (plan.intent.replicas !== null && plan.intent.replicas !== undefined) {
    return `Replicas ${plan.intent.replicas}`;
  }
  return plan.summary;
}

function createPolicyList(policy) {
  const list = document.createElement("ul");
  list.className = "policy-list";

  if (policy.reasons.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No policy blocks";
    list.append(item);
    return list;
  }

  for (const reason of policy.reasons) {
    const item = document.createElement("li");
    item.textContent = reason;
    list.append(item);
  }

  return list;
}

async function approvePlan(planId) {
  const approvedBy = approvedByInput.value.trim() || "local-user";
  await requestJson(`/plans/${planId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ approved_by: approvedBy }),
  });
  await loadPendingApprovals();
}

async function rejectPlan(planId) {
  await requestJson(`/plans/${planId}/reject`, {
    method: "POST",
  });
  await loadPendingApprovals();
}

function renderApprovalItem(item) {
  const plan = item.plan;
  const article = document.createElement("article");
  article.className = "approval-item";

  const content = document.createElement("div");
  content.className = "approval-content";
  content.append(createTextElement("h2", "plan-title", formatPlanTitle(plan)));
  content.append(createTextElement("p", "plan-summary", plan.summary));
  content.append(createTextElement("p", "plan-meta", formatPlanDetails(plan)));
  content.append(createPolicyList(item.policy));

  const actions = document.createElement("div");
  actions.className = "approval-actions";

  const approveButton = document.createElement("button");
  approveButton.type = "button";
  approveButton.className = "button primary";
  approveButton.textContent = "Approve";
  approveButton.addEventListener("click", () => approvePlan(plan.plan_id));

  const rejectButton = document.createElement("button");
  rejectButton.type = "button";
  rejectButton.className = "button danger";
  rejectButton.textContent = "Reject";
  rejectButton.addEventListener("click", () => rejectPlan(plan.plan_id));

  actions.append(approveButton, rejectButton);
  article.append(content, actions);
  return article;
}

function renderEmptyState() {
  approvalList.replaceChildren(
    createTextElement("p", "empty-state", "No pending approvals")
  );
}

async function loadPendingApprovals() {
  setQueueStatus("Loading");
  refreshButton.disabled = true;

  try {
    const approvals = await readJsonResponse(
      await fetch("/approvals/pending?limit=25")
    );
    approvalList.replaceChildren(...approvals.map(renderApprovalItem));

    if (approvals.length === 0) {
      renderEmptyState();
    }

    setQueueStatus(`${approvals.length} pending`);
  } catch (error) {
    approvalList.replaceChildren(
      createTextElement("p", "error-state", error.message)
    );
    setQueueStatus("Unavailable");
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", loadPendingApprovals);
loadPendingApprovals();
