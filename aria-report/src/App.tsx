import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { Toaster } from "sonner";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { useTheme } from "@/hooks/useTheme";
import { ensureApiKey } from "@/lib/api";

// Restrained, native-feeling transition: a short fade with a 6px rise.
const pageVariants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.32, 0.72, 0, 1] } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
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
    <MotionConfig reducedMotion="user">
    <div className="flex h-screen overflow-hidden bg-aria-bg">
      <AppSidebar theme={theme} onToggleTheme={toggle} />
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* initial={false}: the app opens settled; only route changes animate */}
        <AnimatePresence mode="wait" initial={false}>
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
    </MotionConfig>
  );
}
