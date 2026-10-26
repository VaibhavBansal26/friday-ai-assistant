import { motion, useReducedMotion } from "motion/react";
import type { AssistantState } from "../store/app";

export function VoiceOrb({ state }: { state: AssistantState }) {
  const reduced = useReducedMotion();
  const active = ["listening", "thinking", "acting", "speaking"].includes(state);
  return (
    <div className="orb-wrap" role="status" aria-live="polite">
      <motion.div
        className={`orb orb--${state.replaceAll(" ", "-")}`}
        animate={reduced ? {} : { scale: active ? [1, 1.055, 1] : 1 }}
        transition={{ duration: 2.2, repeat: active ? Infinity : 0 }}
        aria-hidden="true"
      />
      <span className="state-label">Friday is {state}</span>
    </div>
  );
}

