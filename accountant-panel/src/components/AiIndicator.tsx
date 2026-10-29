import { Check, Sparkles } from "lucide-react";

export function AiIndicator({ reviewed = false }: { reviewed?: boolean }) {
  return (
    <span className={reviewed ? "reviewed-chip" : "ai-chip"}>
      {reviewed ? (
        <Check aria-hidden="true" />
      ) : (
        <Sparkles aria-hidden="true" />
      )}
      {reviewed ? "Reviewed" : "AI suggested"}
    </span>
  );
}

export function ConfidenceBar({ confidence }: { confidence: unknown }) {
  if (
    confidence == null ||
    typeof confidence === "object" ||
    !Number.isFinite(Number(confidence)) ||
    Number(confidence) < 0 ||
    Number(confidence) > 1
  )
    return <span className="muted">Not supplied by OCR</span>;
  const percent = Number(confidence) * 100;
  return (
    <div
      className="confidence"
      data-level={percent < 60 ? "low" : percent <= 85 ? "medium" : "high"}
    >
      <span>{percent.toFixed(1)}% confidence</span>
      <div
        className="confidence-track"
        role="meter"
        aria-label="AI extraction confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <div className="confidence-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
