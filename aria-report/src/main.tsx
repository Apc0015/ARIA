import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import App from "./App";
import Dashboard from "./pages/Dashboard";
import Launch from "./pages/Launch";
import Monitor from "./pages/Monitor";
import Report from "./pages/Report";
import Sources from "./pages/Sources";
import Settings from "./pages/Settings";

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000 } },
});

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "launch", element: <Launch /> },
      { path: "monitor", element: <Monitor /> },
      { path: "monitor/:runId", element: <Monitor /> },
      { path: "report", element: <Report /> },
      { path: "report/:runId", element: <Report /> },
      { path: "sources", element: <Sources /> },
      { path: "settings", element: <Settings /> },
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
