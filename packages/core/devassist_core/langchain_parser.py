import re

from devassist_core.schemas import DeploymentAction, PipelineIntent


class DeterministicLangChainParser:
    """A LangChain-shaped parser stub that never executes parsed text."""

    def parse(self, text: str) -> PipelineIntent:
        normalized = text.lower()

        if normalized.startswith("deploy "):
            return PipelineIntent(
                action=DeploymentAction.DEPLOY,
                app=_find_after(normalized, "deploy") or "unknown",
                namespace=_find_after(normalized, "to") or "dev",
                image=_find_after(text, "image"),
                raw_text=text,
            )

        if normalized.startswith("scale "):
            replicas_match = re.search(r"\b(\d+)\s+replicas?\b", normalized)
            return PipelineIntent(
                action=DeploymentAction.SCALE,
                app=_find_after(normalized, "scale") or "unknown",
                namespace=_find_after(normalized, "in") or "dev",
                replicas=int(replicas_match.group(1)) if replicas_match else 1,
                raw_text=text,
            )

        return PipelineIntent(
            action=DeploymentAction.STATUS,
            app=_find_after(normalized, "status") or "unknown",
            namespace="dev",
            raw_text=text,
        )


def _find_after(text: str, word: str) -> str | None:
    match = re.search(rf"\b{re.escape(word)}\s+([^\s]+)", text, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip().strip(".,")
    return value or None
