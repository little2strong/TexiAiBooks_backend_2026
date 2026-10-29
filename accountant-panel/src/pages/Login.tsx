import { useEffect, useState } from "react";
import { Alert, Button, Form, Input, Segmented } from "antd";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Fingerprint,
  Mail,
  ScanLine,
  ShieldCheck,
  Sparkles,
  LockKeyhole,
} from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, request } from "../api/client";
import { authProvider } from "../api/providers";
import { useSession } from "../auth/context";
import { ThemeToggle } from "../components/ThemeToggle";
import { LoginShowcase } from "../components/LoginShowcase";
import "./login.css";

type Mode = "login" | "forgot" | "reset";
export function Login() {
  const active = useSession();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  useEffect(() => {
    if (!challenge) return;
    const deadline = Date.now() + seconds * 1000;
    const timer = setInterval(
      () => setSeconds(Math.max(0, Math.ceil((deadline - Date.now()) / 1000))),
      1000,
    );
    return () => clearInterval(timer);
    // The challenge's lifetime is fixed when it is issued.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [challenge]);
  const changeMode = (next: Mode) => {
    form.resetFields();
    setChallenge(null);
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
        setNotice("Password updated. Sign in with your authenticator.");
      } else if (!challenge) {
        const result = await api.login(values.email, values.password);
        form.resetFields();
        setSeconds(result.expires_in);
        setChallenge(result.challenge_id);
      } else {
        const result = await authProvider.login({
          challengeId: challenge,
          code: values.code,
        });
        form.resetFields(["code"]);
        if (!result.success) throw result.error;
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
                {challenge ? (
                  <Fingerprint aria-hidden="true" />
                ) : (
                  <LockKeyhole aria-hidden="true" />
                )}
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
                  : challenge
                    ? "Verify it’s you"
                    : "Welcome back"}
            </h2>
            <p className="muted">
              {mode === "forgot"
                ? "We’ll help you get back to your workspace."
                : mode === "reset"
                  ? "Paste the recovery token from your email. Your authenticator stays enabled."
                  : challenge
                    ? "Enter the six-digit code from your authenticator app."
                    : "Your drivers’ books. Your expertise. All in one place."}
            </p>
            {mode === "login" && (
              <ol className="login-steps" aria-label="Sign-in progress">
                <li
                  className={!challenge ? "current-step" : "complete-step"}
                  aria-current={!challenge ? "step" : undefined}
                >
                  <span>{challenge ? <Check aria-hidden="true" /> : "1"}</span>
                  Sign in
                </li>
                <li
                  className={challenge ? "current-step" : ""}
                  aria-current={challenge ? "step" : undefined}
                >
                  <span>2</span>Verify identity
                </li>
              </ol>
            )}
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
              {!challenge && mode !== "reset" && (
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
              {!challenge && mode !== "forgot" && (
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
              {challenge && (
                <>
                  <Form.Item
                    name="code"
                    label="Authentication code"
                    rules={[
                      {
                        required: true,
                        pattern: /^[0-9]{6}$/,
                        message: "Enter all six digits",
                      },
                    ]}
                  >
                    <Input
                      size="large"
                      className="otp-input"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      autoFocus
                    />
                  </Form.Item>
                  <p className="muted" aria-live="polite">
                    {seconds > 0
                      ? `Challenge expires in ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`
                      : "Challenge expired. Start sign-in again."}
                  </p>
                </>
              )}
              {mode === "login" && !challenge && (
                <div className="login-form-options">
                  <span>
                    <Fingerprint aria-hidden="true" /> Two-step sign-in
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
                disabled={Boolean(challenge && !seconds)}
              >
                {mode === "forgot"
                  ? "Send recovery instructions"
                  : mode === "reset"
                    ? "Update password"
                    : challenge
                      ? "Verify & sign in"
                      : "Continue securely"}
              </Button>
            </Form>
            {(mode !== "login" || challenge) && (
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
                For authorised staff. Sign-ins are verified and financial
                actions are recorded.
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
