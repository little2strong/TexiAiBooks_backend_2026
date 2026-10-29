import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import {
  App,
  Alert,
  Avatar,
  Button,
  Checkbox,
  ConfigProvider,
  Drawer,
  Form,
  Input,
  Modal,
  Select,
  Skeleton,
  Space,
  Switch,
  Tabs,
  Tooltip,
  type ThemeConfig,
} from "antd";
import {
  ArrowLeft,
  ArrowRight,
  FileCheck2,
  Plus,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ThemeToggle } from "../components/ThemeToggle";
import { StatusBadge } from "../components/StatusBadge";
import { AiIndicator, ConfidenceBar } from "../components/AiIndicator";
import { getAntdTheme } from "../theme/antd-theme";
import {
  CountUp,
  feedbackDurationSeconds,
  useReducedMotion,
} from "../theme/motion";
import { money } from "../lib/format";
import { ThemeChart } from "../components/ThemeChart";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="surface preview-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function ComponentExamples({ mode }: { mode: "light" | "dark" }) {
  const { notification } = App.useApp();
  const [modal, setModal] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [compact, setCompact] = useState(false);
  const [replay, setReplay] = useState(0);
  const [selected, setSelected] = useState(false);
  const [status, setStatus] = useState("in_review");
  return (
    <>
      <Section title="Palette & typography">
        <div className="swatch-grid">
          {[
            ["brand", "Taxi amber"],
            ["ink", "Brand ink"],
            ["income", "Income"],
            ["expense", "Expense"],
            ["info", "Information"],
            ["ai", "AI assistant"],
          ].map(([tone, name]) => (
            <div key={tone}>
              <div className={`swatch swatch-${tone}`} />
              <span>{name}</span>
            </div>
          ))}
        </div>
        <p className="muted">
          Inter for the workspace. JetBrains Mono for financial values.
        </p>
        <span className="numeric">£12,345.67 · 4,820 miles</span>
      </Section>
      <Section title="Buttons & interaction states">
        <div className="preview-row">
          <Button type="primary" icon={<Plus />}>
            Primary action
          </Button>
          <Button>Secondary</Button>
          <Button type="text">Ghost</Button>
          <Button danger>Reject</Button>
        </div>
        <div className="preview-row">
          <Button type="primary" loading>
            Saving changes
          </Button>
          <Button disabled>Disabled</Button>
          <Button type="primary" disabled>
            Unavailable
          </Button>
          <Button size="small">Compact</Button>
          <Tooltip title="Review the evidence before approving">
            <Button
              icon={<FileCheck2 />}
              aria-label={`${mode} review tooltip`}
            />
          </Tooltip>
        </div>
      </Section>
      <Section title="Workflow statuses">
        <div className="preview-row">
          {[
            "new",
            "in_review",
            "waiting_on_driver",
            "ready_to_file",
            "filed",
            "rejected",
            "overdue",
          ].map((item) => (
            <StatusBadge key={item} status={item} />
          ))}
        </div>
      </Section>
      <Section title="KPI & financial values">
        <div className="preview-kpi">
          <div>
            <span className="muted">Illustrative income</span>
            <strong className="numeric">£12,345.67</strong>
            <span className="reviewed-chip">↗ 8.2% this month</span>
          </div>
          <svg
            className="sparkline"
            viewBox="0 0 120 36"
            aria-label="Illustrative rising income"
            role="img"
          >
            <path d="M0 30 L15 25 L30 28 L45 16 L60 20 L75 10 L90 14 L105 5 L120 2" />
          </svg>
        </div>
        <p className="expense-text numeric">−£245.50</p>
      </Section>
      <Section title="Forms & validation">
        <Form layout="vertical" requiredMark={false}>
          <Form.Item label={`Merchant (${mode})`} htmlFor={`${mode}-merchant`}>
            <Input id={`${mode}-merchant`} placeholder="Enter merchant name" />
          </Form.Item>
          <Form.Item label={`Category (${mode})`} htmlFor={`${mode}-category`}>
            <Select
              id={`${mode}-category`}
              defaultValue="fuel"
              options={[
                { value: "fuel", label: "Fuel" },
                { value: "insurance", label: "Insurance" },
              ]}
            />
          </Form.Item>
          <Form.Item
            label={`Amount (${mode})`}
            htmlFor={`${mode}-amount`}
            validateStatus="error"
            help="⚠ Enter an amount with up to two decimal places."
          >
            <Input
              id={`${mode}-amount`}
              prefix="£"
              defaultValue="12.345"
              aria-invalid="true"
            />
          </Form.Item>
          <p className="muted">Helper text stays readable in both themes.</p>
        </Form>
      </Section>
      <Section title="Tables, selection & density">
        <div className="preview-row">
          <Switch
            checked={compact}
            onChange={setCompact}
            aria-label={`${mode} compact rows`}
          />
          <span>Compact rows</span>
        </div>
        <div className={`table-scroll ${compact ? "table-compact" : ""}`}>
          <table>
            <caption className="sr-only">Illustrative review records</caption>
            <thead>
              <tr>
                <th scope="col">Select</th>
                <th scope="col">Driver</th>
                <th scope="col">Review</th>
                <th scope="col" data-numeric="true">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              <tr data-selected={selected}>
                <td>
                  <Checkbox
                    checked={selected}
                    onChange={(event) => setSelected(event.target.checked)}
                    aria-label={`${mode} select example driver`}
                  />
                </td>
                <td>
                  <span className="driver-cell">
                    <Avatar className="driver-avatar">AH</Avatar>
                    <strong>Alex Harris</strong>
                  </span>
                </td>
                <td>
                  <StatusBadge status={status} />
                </td>
                <td data-numeric="true">
                  <span className="money-cell">{money(123450)}</span>
                </td>
              </tr>
              <tr>
                <td />
                <td>Jamie Wilson</td>
                <td>
                  <StatusBadge status="filed" />
                </td>
                <td data-numeric="true">
                  <span className="money-cell expense-text">
                    {money(-24550)}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>
      <Section title="AI provenance & confidence">
        <div className="preview-row">
          <AiIndicator />
          <AiIndicator reviewed />
          <span
            className="ai-thinking"
            role="status"
            aria-label="AI is thinking"
          >
            <Sparkles />
            <i />
            <i />
            <i />
          </span>
        </div>
        <Space orientation="vertical" className="full-width">
          <ConfidenceBar confidence={0.48} />
          <ConfidenceBar confidence={0.76} />
          <ConfidenceBar confidence={0.96} />
        </Space>
      </Section>
      <Section title="Chart palette · illustrative data">
        <ThemeChart />
        <div className="chart-legend">
          <span>Income · green</span>
          <span>Expense · red</span>
          <span>Tax · blue</span>
          <span>Mileage · amber</span>
          <span>AI estimate · dashed purple</span>
        </div>
      </Section>
      <Section title="Feedback, overlays & motion">
        <Space orientation="vertical" className="full-width">
          <Alert type="info" title="New evidence is ready to review" showIcon />
          <Alert
            type="warning"
            title="Waiting for driver information"
            showIcon
          />
          <Alert type="error" title="A filing reference is required" showIcon />
          <Alert type="success" title="Your review has been saved" showIcon />
        </Space>
        <div className="preview-row">
          <Button onClick={() => setModal(true)}>Open modal</Button>
          <Button onClick={() => setDrawer(true)}>Open drawer</Button>
          <Button
            onClick={() => {
              const previous = status;
              setStatus("ready_to_file");
              notification.success({
                title: "Review approved",
                description: "Example record is ready to file.",
                duration: feedbackDurationSeconds,
                placement: "bottomRight",
                actions: (
                  <Button
                    size="small"
                    onClick={() => {
                      setStatus(previous);
                      notification.destroy();
                    }}
                  >
                    Undo
                  </Button>
                ),
              });
            }}
          >
            Preview toast & Undo
          </Button>
        </div>
        <Tabs
          items={[
            {
              key: "one",
              label: "Overview",
              children: "Amber underline follows the active tab.",
            },
            {
              key: "two",
              label: "Evidence",
              children: "Tab changes use the shared motion tokens.",
            },
          ]}
        />
        <div className="preview-row">
          <Button onClick={() => setReplay((value) => value + 1)}>
            Replay motion
          </Button>
          <span className="numeric" key={replay}>
            <CountUp value={1248} />
          </span>
        </div>
        <div key={`motion-${replay}`} className="motion-demo row-flash">
          A subtle entrance and record highlight.
        </div>
        <Skeleton active paragraph={{ rows: 2 }} />
        <Modal
          title="Review evidence"
          getContainer={() =>
            document.querySelector<HTMLElement>(
              `.theme-preview[data-theme="${mode}"]`,
            )!
          }
          open={modal}
          onCancel={() => setModal(false)}
          onOk={() => setModal(false)}
        >
          <p>
            This example uses the modal radius, elevation and motion tokens.
          </p>
        </Modal>
        <Drawer
          title="Receipt review"
          getContainer={() =>
            document.querySelector<HTMLElement>(
              `.theme-preview[data-theme="${mode}"]`,
            )!
          }
          open={drawer}
          onClose={() => setDrawer(false)}
        >
          <AiIndicator />
          <p>
            Extracted fields appear beside the private receipt in the workspace.
          </p>
          <ConfidenceBar confidence={0.92} />
        </Drawer>
      </Section>
      <Section title="Empty state">
        <div className="empty-state">
          <FileCheck2 aria-hidden="true" />
          <p>No receipts are waiting for review.</p>
          <Button
            type="primary"
            icon={<ArrowRight />}
            onClick={() => setDrawer(true)}
          >
            View review example
          </Button>
        </div>
      </Section>
    </>
  );
}

function ThemePreview({ mode }: { mode: "light" | "dark" }) {
  const root = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();
  const [config, setConfig] = useState<ThemeConfig>();
  useLayoutEffect(() => {
    if (root.current)
      setConfig(getAntdTheme(mode === "dark", reducedMotion, root.current));
  }, [mode, reducedMotion]);
  return (
    <div
      ref={root}
      className="theme-preview"
      data-theme={mode}
      aria-label={`${mode} theme examples`}
    >
      <ConfigProvider theme={config} getPopupContainer={() => root.current!}>
        <App notification={{ getContainer: () => root.current! }}>
          <h2>{mode === "light" ? "Light workspace" : "Dark workspace"}</h2>
          <ComponentExamples mode={mode} />
        </App>
      </ConfigProvider>
    </div>
  );
}

export function StyleguidePage() {
  return (
    <main className="styleguide-page">
      <header className="styleguide-header">
        <div>
          <Link to="/" className="back-link">
            <ArrowLeft /> Return to workspace
          </Link>
          <span className="eyebrow">TAXIAIBOOKS · VISUAL SYSTEM</span>
          <h1>One brand. Every detail.</h1>
          <p className="muted">
            Components, workflow states and motion in both modes. All records
            here are illustrative.
          </p>
        </div>
        <ThemeToggle />
      </header>
      <div className="styleguide-grid">
        <ThemePreview mode="light" />
        <ThemePreview mode="dark" />
      </div>
    </main>
  );
}
