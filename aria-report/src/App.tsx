import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Toaster } from "sonner";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { useTheme } from "@/hooks/useTheme";
import { ensureApiKey } from "@/lib/api";

const pageVariants = {
  initial: { opacity: 0, x: 16 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.18, ease: "easeOut" } },
  exit: { opacity: 0, x: -8, transition: { duration: 0.12 } },
};

export default function App() {
  const location = useLocation();
  const { theme, toggle } = useTheme();

  // Fetch the server-generated API key once on mount and inject it into
  // every subsequent request via api.ts's module-level store.
  useEffect(() => {
    ensureApiKey()
      .catch(() => {/* server unreachable — requests will 401 until resolved */});
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-aria-bg">
      <AppSidebar theme={theme} onToggleTheme={toggle} />
      <main className="flex-1 flex flex-col overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            className="flex-1 flex flex-col overflow-hidden"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <Toaster
        theme={theme}
        toastOptions={{
          style: {
            background: "var(--aria-surface)",
            border: "1px solid var(--aria-border)",
            color: "var(--aria-text-1)",
          },
        }}
      />
    </div>
  );
}
