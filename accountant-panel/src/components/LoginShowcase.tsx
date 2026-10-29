import {
  ArrowRight,
  Check,
  ReceiptText,
  ScanLine,
  Sparkles,
} from "lucide-react";

/** A workflow illustration, with no account data or simulated financial totals. */
export function LoginShowcase() {
  return (
    <figure
      className="login-showcase"
      aria-label="Workflow illustration: capture a receipt, review AI suggestions, then confirm the details."
    >
      <div className="showcase-heading">
        <span>
          <span className="showcase-dot" /> A LITTLE LESS ADMIN
        </span>
        <span>Workflow preview</span>
      </div>
      <div className="showcase-cards">
        <div className="capture-slip">
          <div className="capture-slip-icon">
            <ReceiptText aria-hidden="true" />
          </div>
          <strong>Every detail counts.</strong>
          <span className="capture-slip-subtitle">
            Start with the evidence.
          </span>
          <div className="capture-lines" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div className="capture-slip-footer">
            <ScanLine aria-hidden="true" />
            <span>Receipt captured</span>
            <Check aria-hidden="true" />
          </div>
        </div>
        <div className="showcase-transfer" aria-hidden="true">
          <ArrowRight />
        </div>
        <div className="review-slip">
          <div className="review-slip-heading">
            <span className="showcase-ai">
              <Sparkles aria-hidden="true" /> AI suggested
            </span>
            <span className="review-slip-dot" />
          </div>
          <strong>Ready for your expertise.</strong>
          <p>
            The details in one place.
            <br />
            The decision stays with you.
          </p>
          <div className="review-detail">
            <span>Extracted fields</span>
            <Check aria-hidden="true" />
          </div>
          <div className="review-detail">
            <span>Category suggestion</span>
            <Check aria-hidden="true" />
          </div>
          <div className="showcase-reviewed">
            <span>
              <Check aria-hidden="true" /> Reviewed
            </span>
            <span>Human approved</span>
          </div>
        </div>
      </div>
      <figcaption>From the driver's first snap to your final check.</figcaption>
    </figure>
  );
}
