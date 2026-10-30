import { useState } from "react";
import { Alert, Button, Form, Input, Segmented } from "antd";
import {
  ArrowLeft,
  ArrowRight,
  Mail,
  ScanLine,
  ShieldCheck,
  Sparkles,
  LockKeyhole,
} from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import { request } from "../api/client";
import { authProvider } from "../api/providers";
import { useSession } from "../auth/context";
import { session } from '../auth/session';
import { ThemeToggle } from "../components/ThemeToggle";
import { LoginShowcase } from "../components/LoginShowcase";
import "./login.css";

type Mode = "login" | "forgot" | "reset";
export function Login() {
  const active = useSession();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(session.notice() || '');
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const changeMode = (next: Mode) => {
    form.resetFields();
    setError("");
    setNotice("");
    setMode(next);
  };
  const submit = async (values: Record<string, string>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "forgot") {
        await request("/auth/forgot-password", {
          public: true,
          method: "POST",
          body: { email: values.email },
        });
        setNotice("If the account exists, recovery instructions will be sent.");
        form.resetFields();
      } else if (mode === "reset") {
        await request("/auth/reset-password", {
          public: true,
          method: "POST",
          body: { token: values.token, new_password: values.password },
        });
        changeMode("login");
        setNotice("Password updated. Sign in with your email and password.");
      } else {
        const result = await authProvider.login({
          email: values.email,
          password: values.password,
        });
        if (!result.success) throw result.error;
        form.resetFields();
        navigate("/", { replace: true });
      }
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Sign-in could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  };
  if (active) return <Navigate to="/" replace />;
  return (
    <main className="login-page">
      <section
        className="login-story"
        aria-label="TaxiAiBooks accountant workspace"
      >
        <header className="login-brand-header">
          <div className="brand brand-login">
            <span className="brand-mark">
              t<span>.</span>
            </span>
            <span>
              TaxiAiBooks<small>Drive. Snap. Done.</small>
            </span>
          </div>
          <span className="login-edition">Accountant & admin</span>
        </header>
        <div className="login-story-content">
          <div className="login-story-copy">
            <span className="eyebrow">
              <span /> MADE FOR THE PEOPLE BEHIND THE DRIVERS
            </span>
            <h1>
              From busy roads
              <br /> to <span>clear books.</span>
            </h1>
            <p>
              A calmer place to review the details, support your drivers and
              keep every handoff moving.
            </p>
          </div>
          <LoginShowcase />
          <div className="login-benefits">
            <div>
              <ScanLine aria-hidden="true" />
              <strong>Evidence first</strong>
              <span>Every receipt, in context.</span>
            </div>
            <div>
              <Sparkles aria-hidden="true" />
              <strong>AI assisted</strong>
              <span>Your expertise in control.</span>
            </div>
            <div>
              <ShieldCheck aria-hidden="true" />
              <strong>Always traceable</strong>
              <span>A clear trail of every action.</span>
            </div>
          </div>
        </div>
        <footer className="login-story-footer">
          <span>
            <ShieldCheck aria-hidden="true" /> Private by design. Accountable by
            default.
          </span>
          <span>
            Built for the road ahead <ArrowRight aria-hidden="true" />
          </span>
        </footer>
      </section>
      <section className="login-form-section" aria-label="Staff sign in">
        <header className="login-form-topbar">
          <span>
            <span className="login-status-dot" /> YOUR SECURE WORKSPACE
          </span>
          <ThemeToggle />
        </header>
        <div className="login-form-center">
          <div className="login-form-wrap">
            <div className="login-card-heading">
              <span className="login-entry-icon">
                <LockKeyhole aria-hidden="true" />
              </span>
              <span className="secure-chip">
                {mode === "login" ? "STAFF ACCESS" : "ACCOUNT RECOVERY"}
              </span>
            </div>
            <h2>
              {mode === "forgot"
                ? "Forgot your password?"
                : mode === "reset"
                  ? "Set a new password"
                  : "Welcome back"}
            </h2>
            <p className="muted">
              {mode === "forgot"
                ? "We’ll help you get back to your workspace."
                : mode === "reset"
                  ? "Paste the recovery token from your email to set a new password."
                  : "Your drivers’ books. Your expertise. All in one place."}
            </p>
            {error && (
              <Alert
                type="error"
                showIcon
                title={error}
                className="form-alert"
              />
            )}
            {notice && (
              <Alert
                type="success"
                showIcon
                title={notice}
                className="form-alert"
              />
            )}
            {mode === "reset" && (
              <Alert
                type="info"
                title="Keep the recovery token private"
                description="Paste the token into the field below; do not put it in the address bar."
                className="form-alert"
              />
            )}
            <Form
              form={form}
              layout="vertical"
              onFinish={submit}
              requiredMark={false}
            >
              {mode !== "reset" && (
                <Form.Item
                  name="email"
                  label="Work email"
                  rules={[
                    {
                      required: true,
                      type: "email",
                      message: "Enter your work email address",
                    },
                  ]}
                >
                  <Input
                    prefix={<Mail aria-hidden="true" />}
                    size="large"
                    type="email"
                    autoComplete="username"
                    placeholder="you@yourpractice.co.uk"
                    maxLength={254}
                  />
                </Form.Item>
              )}
              {mode !== "forgot" && (
                <>
                  {mode === "reset" && (
                    <Form.Item
                      name="token"
                      label="Recovery token"
                      rules={[{ required: true }]}
                    >
                      <Input.Password size="large" autoComplete="off" />
                    </Form.Item>
                  )}
                  <Form.Item
                    name="password"
                    label={mode === "reset" ? "New password" : "Password"}
                    rules={[
                      {
                        required: true,
                        min: mode === "reset" ? 8 : 1,
                        max: 128,
                      },
                    ]}
                  >
                    <Input.Password
                      prefix={<LockKeyhole aria-hidden="true" />}
                      size="large"
                      autoComplete={
                        mode === "reset" ? "new-password" : "current-password"
                      }
                      placeholder={
                        mode === "reset"
                          ? "Create a strong password"
                          : "Enter your password"
                      }
                    />
                  </Form.Item>
                  {mode === "reset" && (
                    <Form.Item
                      name="confirmation"
                      label="Confirm new password"
                      dependencies={["password"]}
                      rules={[
                        { required: true },
                        ({ getFieldValue }) => ({
                          validator: (_, value: string) =>
                            value === getFieldValue("password")
                              ? Promise.resolve()
                              : Promise.reject(
                                  new Error("Passwords must match"),
                                ),
                        }),
                      ]}
                    >
                      <Input.Password
                        size="large"
                        autoComplete="new-password"
                      />
                    </Form.Item>
                  )}
                </>
              )}
              {mode === "login" && (
                <div className="login-form-options">
                  <span>
                    <LockKeyhole aria-hidden="true" /> Staff workspace
                  </span>
                  <Button type="link" onClick={() => changeMode("forgot")}>
                    Forgot password?
                  </Button>
                </div>
              )}
              <Button
                block
                size="large"
                type="primary"
                htmlType="submit"
                icon={<ArrowRight aria-hidden="true" />}
                iconPlacement="end"
                loading={busy}
              >
                {mode === "forgot"
                  ? "Send recovery instructions"
                  : mode === "reset"
                    ? "Update password"
                    : "Sign in"}
              </Button>
            </Form>
            {mode !== "login" && (
              <Button
                type="link"
                icon={<ArrowLeft />}
                className="forgot-link"
                onClick={() => changeMode("login")}
              >
                Back to sign in
              </Button>
            )}
            {mode !== "login" && (
              <Segmented
                value={mode}
                block
                options={[
                  { value: "forgot", label: "Request recovery" },
                  { value: "reset", label: "I have a token" },
                ]}
                onChange={(value) => changeMode(value as Mode)}
              />
            )}
            <div className="login-card-note">
              <LockKeyhole aria-hidden="true" />
              <span>Your session and financial data stay private.</span>
            </div>
          </div>
          <div className="login-help">
            <ShieldCheck aria-hidden="true" />
            <div>
              <strong>A workspace you can trust.</strong>
              <p>
                For authorised staff. Financial views and changes are recorded.
              </p>
            </div>
          </div>
        </div>
        <footer className="login-footer">
          <span>TaxiAiBooks · Accountant & Admin</span>
          <span>Drive. Snap. Done.</span>
        </footer>
      </section>
    </main>
  );
}
