import { lazy, Suspense, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { Refine } from "@refinedev/core";
import { QueryClient } from "@tanstack/react-query";
import { App as AntApp, Result, Button, Skeleton } from "antd";
import { BrowserRouter, Route, Routes, Link, useLocation } from "react-router-dom";
import { PanelBoundary } from './components/States';
import interFont from '@fontsource/inter/files/inter-latin-400-normal.woff2?url';
import { dataProvider, authProvider } from "./api/providers";
import { can, type Action } from "./auth/permissions";
import { session } from "./auth/session";
import { ProtectedWorkspace } from "./auth/context";
import { WorkspaceLayout } from "./components/WorkspaceLayout";
import { Login } from "./pages/Login";
import { DashboardPage } from "./pages/Dashboard";
import { HandoffsPage } from "./pages/Handoffs";
import { DriversPage } from "./pages/Drivers";
import { DriverProfilePage } from "./pages/DriverProfile";
import { ThemeProvider } from "./theme/ThemeProvider";
import { feedbackDurationSeconds } from "./theme/motion";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "./styles.css";
const StyleguidePage = lazy(() =>
  import("./pages/Styleguide").then((module) => ({
    default: module.StyleguidePage,
  })),
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 15000,
      gcTime: 0,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
});
session.subscribe(() => {
  if (!session.get()) {
    void queryClient.cancelQueries();
    queryClient.clear();
  }
});

function RoutePanel({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <PanelBoundary resetKey={location.pathname}>{children}</PanelBoundary>;
}
function Panel() {
  return (
    <ThemeProvider>
      <AntApp
        message={{ duration: feedbackDurationSeconds }}
        notification={{
          placement: "bottomRight",
          duration: feedbackDurationSeconds,
        }}
      >
        <BrowserRouter>
          <Refine
            dataProvider={dataProvider}
            authProvider={authProvider}
            accessControlProvider={{
              can: async ({ action }) => ({
                can: can(
                  session.get()?.staff.role,
                  ({ list: "read", show: "read", create: "edit", edit: "edit" }[
                    action
                  ] || action) as Action,
                ),
              }),
            }}
            resources={[
              { name: "drivers", list: "/drivers", show: "/drivers/:id" },
              { name: "handoffs", list: "/handoffs" },
            ]}
            options={{
              disableTelemetry: true,
              reactQuery: { clientConfig: queryClient },
            }}
          >
            <RoutePanel><Routes>
              <Route path="/login" element={<Login />} />
              <Route
                path="/styleguide"
                element={
                  <Suspense
                    fallback={
                      <div
                        className="state-padding"
                        aria-label="Loading styleguide"
                      >
                        <Skeleton active />
                      </div>
                    }
                  >
                    <StyleguidePage />
                  </Suspense>
                }
              />
              <Route
                element={
                  <ProtectedWorkspace>
                    <WorkspaceLayout />
                  </ProtectedWorkspace>
                }
              >
                <Route index element={<RoutePanel><DashboardPage /></RoutePanel>} />
                <Route path="handoffs" element={<RoutePanel><HandoffsPage /></RoutePanel>} />
                <Route path="drivers" element={<RoutePanel><DriversPage /></RoutePanel>} />
                <Route path="drivers/:id" element={<RoutePanel><DriverProfilePage /></RoutePanel>} />
              </Route>
              <Route
                path="*"
                element={
                  <Result
                    status="404"
                    title="Page not found"
                    extra={
                      <Link to="/">
                        <Button>Return to workspace</Button>
                      </Link>
                    }
                  />
                }
              />
            </Routes></RoutePanel>
          </Refine>
        </BrowserRouter>
      </AntApp>
    </ThemeProvider>
  );
}

const preload = document.createElement('link');
preload.rel = 'preload'; preload.as = 'font'; preload.type = 'font/woff2'; preload.crossOrigin = 'anonymous'; preload.href = interFont;
if (!document.querySelector(`link[href="${interFont}"]`)) document.head.append(preload);
async function mount() {
  if (import.meta.env.DEV && import.meta.env.VITE_UI_DIAGNOSTICS === 'true') await import('./ui-diagnostics');
  const root = import.meta.hot?.data.root || createRoot(document.getElementById('root')!);
  if (import.meta.hot) import.meta.hot.data.root = root;
  root.render(<PanelBoundary><Panel /></PanelBoundary>);
}
void mount();
