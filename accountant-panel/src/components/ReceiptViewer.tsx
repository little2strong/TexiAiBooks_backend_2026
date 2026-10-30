import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  App,
  Button,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Spin,
} from "antd";
import { Check, X, Undo2, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { api } from "../api/client";
import { useSession, useWorkspace } from "../auth/context";
import { can } from "../auth/permissions";
import { currencyInput, currencyPence, label, money } from "../lib/format";
import { QueryState } from "./States";
import { StatusBadge } from "./StatusBadge";
import { AiIndicator, ConfidenceBar } from "./AiIndicator";
import type { Receipt } from "../api/types";
import { feedbackDurationSeconds } from "../theme/motion";
import { RecordAudit } from './RecordAudit';

export function ReceiptViewer({
  driverId,
  receiptId,
  close,
  next,
}: {
  driverId: string;
  receiptId: string;
  close: () => void;
  next?: () => void;
}) {
  const { config } = useWorkspace();
  const staff = useSession()!.staff;
  const { message, notification, modal } = App.useApp();
  const cache = useQueryClient();
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mediaError, setMediaError] = useState("");
  const [zoom, setZoom] = useState(100);
  const [form] = Form.useForm();
  const result = useQuery({
    queryKey: ["receipt", driverId, receiptId],
    queryFn: ({ signal }) => api.receipt(driverId, receiptId, signal),
  });
  const receipt = result.data;
  useEffect(() => {
    if (!receipt) return;
    form.setFieldsValue({
      category_id:
        receipt.category_id || receipt.extraction?.suggested_category_id,
      percent: Number(receipt.business_use_percent || "100"),
      reason: "",
      merchant: receipt.merchant || "",
      occurred_on: receipt.occurred_on || "",
      amount_gbp: receipt.amount_pence
        ? currencyInput(receipt.amount_pence)
        : undefined,
    });
  }, [receipt, form]);
  useEffect(() => {
    setUrl(null);
    setMediaError("");
    if (!receipt || !["clean", "generated"].includes(receipt.scan_status))
      return;
    const controller = new AbortController();
    let privateUrl: string | undefined;
    void api
      .blob(
        `/drivers/${driverId}/documents/${receipt.file_id}/content`,
        controller.signal,
      )
      .then((blob) => {
        if (!controller.signal.aborted) {
          privateUrl = URL.createObjectURL(blob);
          setUrl(privateUrl);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setMediaError((error as Error).message);
      });
    return () => {
      controller.abort();
      if (privateUrl) URL.revokeObjectURL(privateUrl);
    };
  }, [receipt, driverId]);
  const review = useCallback(
    async (decision: "approve" | "reject") => {
      if (
        !receipt ||
        busy ||
        !can(staff.role, "edit") ||
        receipt.review_status === "confirmed"
      )
        return;
      let values: { category_id: string; percent: number; reason: string };
      try {
        values = await form.validateFields();
      } catch {
        return;
      }
      const extracted = form.getFieldsValue([
        "merchant",
        "occurred_on",
        "amount_gbp",
      ]);
      let enteredPence: number;
      try { enteredPence = currencyPence(extracted.amount_gbp || ''); }
      catch (error) { void message.warning((error as Error).message); return; }
      if (
        extracted.merchant !== (receipt.merchant || "") ||
        extracted.occurred_on !== (receipt.occurred_on || "") ||
        enteredPence !== receipt.amount_pence
      ) {
        void message.warning(
          "Save the corrected extracted fields before approving or rejecting.",
        );
        return;
      }
      if (decision === 'reject' && !await modal.confirm({ title: 'Exclude this receipt?', content: `Record receipt ${receipt.merchant || receipt.id} as excluded with no deduction? Your reason will be audited. A later correction requires reversing the confirmation.`, okText: 'Confirm exclusion', okButtonProps: { danger: true } })) return;
      setBusy(true);
      try {
        const posted = await api.mutate<{
          receipt: Receipt;
          mutation_id: string;
        }>(`/drivers/${driverId}/receipts/${receiptId}/review`, {
          expected_version: receipt.version,
          category_id: values.category_id,
          business_use_percent: String(values.percent),
          reason: values.reason,
          decision,
        });
        await cache.invalidateQueries({
          queryKey: ["receipt", driverId, receiptId],
        });
        await cache.invalidateQueries({ queryKey: ["table"] });
        await cache.invalidateQueries({ queryKey: ["overview", driverId] });
        await cache.invalidateQueries({ queryKey: ["tax", driverId] });
        const notificationKey = `receipt-review-${receiptId}`;
        notification.success({
          key: notificationKey,
          title:
            decision === "approve" ? "Receipt approved" : "Receipt excluded",
          description:
            decision === "approve"
              ? "Confirmed using server eligibility rules."
              : "Recorded as excluded, with no deduction.",
          placement: "bottomRight",
          duration: feedbackDurationSeconds,
          actions: (
            <Button
              size="small"
              icon={<Undo2 />}
              onClick={() => {
                notification.destroy(notificationKey);
                setBusy(true);
                void api
                  .mutate(
                    `/drivers/${driverId}/receipts/${receiptId}/reversals`,
                    {
                      expected_version: posted.receipt.version,
                      mutation_id: posted.mutation_id,
                      reason: `Undo ${decision}: ${values.reason}`.slice(
                        0,
                        500,
                      ),
                    },
                  )
                  .then(async () => {
                    await Promise.all([
                      cache.invalidateQueries({
                        queryKey: ["receipt", driverId, receiptId],
                      }),
                      cache.invalidateQueries({ queryKey: ["table"] }),
                      cache.invalidateQueries({
                        queryKey: ["overview", driverId],
                      }),
                      cache.invalidateQueries({ queryKey: ["tax", driverId] }),
                    ]);
                    void message.success(
                      "Review undone. The exact confirmation was reversed.",
                    );
                  })
                  .catch((error) => {
                    void message.error((error as Error).message);
                  })
                  .finally(() => setBusy(false));
              }}
            >
              Undo
            </Button>
          ),
        });
      } catch (error) {
        void message.error((error as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [
      receipt,
      busy,
      staff.role,
      form,
      driverId,
      receiptId,
      cache,
      message,
      notification,
      modal,
    ],
  );
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (
        event.ctrlKey ||
        event.altKey ||
        event.metaKey ||
        event.repeat ||
        (event.target instanceof HTMLElement &&
          event.target.closest(
            'input,textarea,select,[contenteditable="true"],[role="combobox"]',
          ))
      )
        return;
      const key = event.key.toLowerCase();
      if (key === "n" && next && !busy) {
        event.preventDefault();
        next();
      }
      if ((key === "a" || key === "r") && can(staff.role, "edit")) {
        event.preventDefault();
        void review(key === "a" ? "approve" : "reject");
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [review, next, busy, staff.role]);
  const reverse = async () => {
    if (!receipt?.mutation_id) return;
    let values: { reason: string };
    try {
      values = await form.validateFields(["reason"]);
    } catch {
      return;
    }
    setBusy(true);
    try {
      await api.mutate(`/drivers/${driverId}/receipts/${receiptId}/reversals`, {
        expected_version: receipt.version,
        mutation_id: receipt.mutation_id,
        reason: values.reason,
      });
      await cache.invalidateQueries({
        queryKey: ["receipt", driverId, receiptId],
      });
      await cache.invalidateQueries({ queryKey: ["table"] });
      await cache.invalidateQueries({ queryKey: ["overview", driverId] });
      await cache.invalidateQueries({ queryKey: ["tax", driverId] });
      void message.success(
        "Confirmation reversed. Review the corrected category and confirm again.",
      );
    } catch (error) {
      void message.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const saveFields = async () => {
    if (!receipt || receipt.review_status === "confirmed") return;
    let values: { merchant: string; occurred_on: string; amount_gbp: string };
    try {
      values = await form.validateFields([
        "merchant",
        "occurred_on",
        "amount_gbp",
      ]);
    } catch {
      return;
    }
    setBusy(true);
    try {
      await api.mutate(
        `/drivers/${driverId}/receipts/${receiptId}`,
        {
          merchant: values.merchant,
          occurred_on: values.occurred_on,
          amount_pence: currencyPence(values.amount_gbp),
          expected_version: receipt.version,
        },
        "PATCH",
      );
      await cache.invalidateQueries({
        queryKey: ["receipt", driverId, receiptId],
      });
      await cache.invalidateQueries({ queryKey: ["table"] });
      void message.success("Reviewed fields saved as an unconfirmed draft.");
    } catch (error) {
      void message.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Drawer
      title="Receipt review"
      open
      onClose={busy ? undefined : close}
      size="min(1160px, 96vw)"
      destroyOnHidden
      footer={
        <div className="receipt-footer">
          <span className="muted">
            Shortcuts: A approve · R reject · N next
          </span>
          <Space>
            <RecordAudit driverId={driverId} recordId={receiptId} />
            <Button disabled={!next || busy} onClick={next}>
              Next receipt
            </Button>
            {can(staff.role, "edit") &&
              receipt?.review_status !== "confirmed" && (
                <>
                  <Button
                    danger
                    aria-label="Reject"
                    icon={<X aria-hidden="true" />}
                    loading={busy}
                    onClick={() => void review("reject")}
                  >
                    Reject
                  </Button>
                  <Button
                    type="primary"
                    aria-label="Approve"
                    icon={<Check aria-hidden="true" />}
                    loading={busy}
                    onClick={() => void review("approve")}
                  >
                    Approve
                  </Button>
                </>
              )}
          </Space>
        </div>
      }
    >
      <QueryState
        pending={result.isPending}
        error={result.error}
        retry={result.refetch}
      >
        {receipt && (
          <div className="receipt-grid">
            <div>
              <div className="receipt-zoom">
                <Button
                  aria-label="Zoom out receipt"
                  icon={<ZoomOut />}
                  disabled={
                    zoom <= 100 ||
                    !url ||
                    receipt.mime_type === "application/pdf"
                  }
                  onClick={() => setZoom((value) => Math.max(100, value - 25))}
                />
                <Button
                  aria-label="Reset receipt zoom"
                  icon={<RotateCcw />}
                  disabled={!url || receipt.mime_type === "application/pdf"}
                  onClick={() => setZoom(100)}
                >
                  {zoom}%
                </Button>
                <Button
                  aria-label="Zoom in receipt"
                  icon={<ZoomIn />}
                  disabled={
                    zoom >= 300 ||
                    !url ||
                    receipt.mime_type === "application/pdf"
                  }
                  onClick={() => setZoom((value) => Math.min(300, value + 25))}
                />
              </div>
              <div className="receipt-media">
                {mediaError ? (
                  <Alert
                    type="error"
                    title="Receipt could not be opened"
                    description={mediaError}
                  />
                ) : !["clean", "generated"].includes(receipt.scan_status) ? (
                  <Alert
                    type="warning"
                    title="Evidence is quarantined"
                    description="The private file becomes available after a successful malware scan."
                  />
                ) : !url ? (
                  <Spin description="Loading private evidence" />
                ) : receipt.mime_type === "application/pdf" ? (
                  <iframe
                    title="Private receipt PDF"
                    src={url}
                    sandbox="allow-same-origin"
                  />
                ) : (
                  <div
                    className="receipt-image-frame"
                    tabIndex={0}
                    role="region"
                    aria-label="Receipt image, scroll to pan when zoomed"
                    onPointerDown={(event) => {
                      if (zoom <= 100) return;
                      const target = event.currentTarget;
                      target.setPointerCapture(event.pointerId);
                      target.dataset.dragging = "true";
                    }}
                    onPointerUp={(event) => {
                      event.currentTarget.dataset.dragging = "false";
                    }}
                    onPointerCancel={(event) => {
                      event.currentTarget.dataset.dragging = "false";
                    }}
                    onPointerMove={(event) => {
                      if (event.currentTarget.dataset.dragging !== "true")
                        return;
                      event.currentTarget.scrollLeft -= event.movementX;
                      event.currentTarget.scrollTop -= event.movementY;
                    }}
                  >
                    <img
                      alt="Uploaded receipt evidence"
                      src={url}
                      draggable={false}
                      style={{
                        width: `${zoom}%`,
                        maxWidth: "none",
                        maxHeight: zoom > 100 ? "none" : undefined,
                      }}
                    />
                  </div>
                )}
              </div>
            </div>
            <div className="receipt-fields">
              <Space className="section-gap">
                <StatusBadge status={receipt.review_status} />
                <StatusBadge status={receipt.claim_status} />
              </Space>
              <div className="section-gap">
                {receipt.review_status === "confirmed" ? (
                  <AiIndicator reviewed reviewerName={receipt.reviewerName} />
                ) : (
                  receipt.extraction && <AiIndicator />
                )}
              </div>
              {receipt.extraction && <p className="muted">OCR reason / notes: {receipt.extraction.warnings?.join('; ') || 'No reason supplied by OCR. Confidence is a provider score, not a guarantee of correctness.'}</p>}
              <h2>{receipt.merchant || "Merchant not supplied"}</h2>
              <Descriptions
                column={1}
                size="small"
                items={[
                  {
                    key: "total",
                    label: "Full bill",
                    children: money(receipt.amount_pence),
                  },
                  {
                    key: "date",
                    label: "Date",
                    children: receipt.occurred_on || "Not supplied",
                  },
                  {
                    key: "vat",
                    label: "Extracted VAT",
                    children: money(receipt.vat_pence),
                  },
                  {
                    key: "confidence",
                    label: "AI confidence",
                    children: (
                      <ConfidenceBar
                        confidence={receipt.extraction?.confidence}
                      />
                    ),
                  },
                ]}
              />
              {(receipt.warnings || []).map((warning) => (
                <Alert
                  key={warning}
                  type="warning"
                  title={warning}
                  className="form-alert"
                />
              ))}
              <Form
                form={form}
                layout="vertical"
                requiredMark={false}
                disabled={busy || !can(staff.role, "edit")}
              >
                <Form.Item
                  name="merchant"
                  label="Merchant"
                  rules={[{ required: true, max: 200 }]}
                >
                  <Input
                    disabled={receipt.review_status === "confirmed"}
                    maxLength={200}
                  />
                </Form.Item>
                <Form.Item
                  name="occurred_on"
                  label="Receipt date"
                  rules={[{ required: true }]}
                >
                  <Input
                    type="date"
                    disabled={receipt.review_status === "confirmed"}
                  />
                </Form.Item>
                <Form.Item
                  name="amount_gbp"
                  label="Full bill amount (£)"
                  rules={[
                    { required: true },
                    {
                      validator: (_, value: string) => {
                        try {
                          currencyPence(value);
                          return Promise.resolve();
                        } catch {
                          return Promise.reject(
                            new Error(
                              "Enter a positive amount with up to two decimal places",
                            ),
                          );
                        }
                      },
                    },
                  ]}
                >
                  <InputNumber
                    stringMode
                    min="0.01"
                    precision={2}
                    prefix="£"
                    disabled={receipt.review_status === "confirmed"}
                    className="full-width"
                  />
                </Form.Item>
                {receipt.review_status !== "confirmed" && (
                  <Button
                    onClick={() => void saveFields()}
                    disabled={!can(staff.role, "edit")}
                    loading={busy}
                    className="section-gap"
                  >
                    Save corrected extracted fields
                  </Button>
                )}
                <Form.Item
                  name="category_id"
                  label="Reviewed category"
                  rules={[{ required: true }]}
                >
                  <Select
                    disabled={receipt.review_status === "confirmed"}
                    options={config.categories.map((category) => ({
                      value: category.id,
                      label: label(category.code),
                    }))}
                  />
                </Form.Item>
                <Form.Item
                  name="percent"
                  label="Business use (%)"
                  rules={[{ required: true, type: "number", min: 0, max: 100 }]}
                >
                  <InputNumber
                    min={0}
                    max={100}
                    precision={2}
                    disabled={receipt.review_status === "confirmed"}
                    className="full-width"
                  />
                </Form.Item>
                <Form.Item
                  name="reason"
                  label="Review / correction reason"
                  rules={[{ required: true, min: 3, max: 500 }]}
                >
                  <Input.TextArea maxLength={500} rows={3} />
                </Form.Item>
              </Form>
              {receipt.review_status === "confirmed" && (
                <Alert
                  type="info"
                  title="This receipt is already posted"
                  description="Corrections must reverse this exact confirmation first. Locked accounting periods and later changes can prevent reversal."
                  className="form-alert"
                />
              )}
              {can(staff.role, "edit") &&
                receipt.review_status === "confirmed" && (
                  <Button
                    icon={<Undo2 />}
                    loading={busy}
                    onClick={() => void reverse()}
                  >
                    Reverse confirmation to correct
                  </Button>
                )}
              <p className="muted">
                The backend calculates the deduction and enforces the vehicle
                method and claim rules. Approval does not override eligibility.
              </p>
            </div>
          </div>
        )}
      </QueryState>
    </Drawer>
  );
}
