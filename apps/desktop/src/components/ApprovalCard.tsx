import { ShieldCheck } from "lucide-react";
import type { Approval } from "../lib/api";

export function ApprovalCard({
  approval,
  onDecision,
}: {
  approval: Approval;
  onDecision: (decision: "approved_once" | "rejected") => void;
}) {
  return (
    <section className="approval-card" aria-labelledby="approval-title">
      <div className="approval-icon"><ShieldCheck size={18} /></div>
      <div className="approval-copy">
        <p className="eyebrow">Approval required · Level 3</p>
        <h3 id="approval-title">Action awaiting review</h3>
        <dl>
          <div><dt>Action ID</dt><dd>{approval.action_id.slice(0, 12)}…</dd></div>
          <div><dt>Scope</dt><dd>{approval.scope}</dd></div>
          <div><dt>Status</dt><dd>{approval.status}</dd></div>
        </dl>
        <div className="actions">
          <button className="button button--quiet" onClick={() => onDecision("rejected")}>Reject</button>
          <button className="button button--primary" onClick={() => onDecision("approved_once")}>Approve once</button>
        </div>
      </div>
    </section>
  );
}
