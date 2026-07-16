import { StrictMode, Suspense, lazy } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import App from "./App";

// Route-level code splitting: each page loads on first visit instead of
// shipping one monolithic bundle.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Launch = lazy(() => import("./pages/Launch"));
const Monitor = lazy(() => import("./pages/Monitor"));
const Report = lazy(() => import("./pages/Report"));
const Sources = lazy(() => import("./pages/Sources"));
const Settings = lazy(() => import("./pages/Settings"));

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000 } },
});

const page = (el: ReactNode) => (
  <Suspense
    fallback={
      <div className="flex h-full min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    }
  >
    {el}
  </Suspense>
);

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: page(<Dashboard />) },
      { path: "launch", element: page(<Launch />) },
      { path: "monitor", element: page(<Monitor />) },
      { path: "monitor/:runId", element: page(<Monitor />) },
      { path: "report", element: page(<Report />) },
      { path: "report/:runId", element: page(<Report />) },
      { path: "sources", element: page(<Sources />) },
      { path: "settings", element: page(<Settings />) },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);
