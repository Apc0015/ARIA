import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { Toaster } from "sonner";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";
import { useTheme } from "@/hooks/useTheme";
import { api } from "@/lib/api";

// Restrained, native-feeling transition: a short fade with a 6px rise.
const pageVariants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.32, 0.72, 0, 1] } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
};

function routeName(pathname: string): string {
  const segment = pathname.split("/")[1] || "dashboard";
  return segment.charAt(0).toUpperCase() + segment.slice(1);
}

export default function App() {
  const location = useLocation();
  const { theme, toggle } = useTheme();
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [userEmail, setUserEmail] = useState("");
  const [userRole, setUserRole] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api.auth.me().then((result) => { setUserEmail(result.user.email); setUserRole(result.user.role); setAuthenticated(true); }).catch(() => setAuthenticated(false));
  }, []);

  if (authenticated === null) return <div className="grid h-screen place-items-center text-sm text-aria-text4">Loading workspace...</div>;
  if (!authenticated) return <Navigate to="/login" replace />;

  return (
    <MotionConfig reducedMotion="user">
    <div className="flex h-screen overflow-hidden bg-aria-bg">
      <AppSidebar theme={theme} onToggleTheme={toggle} userEmail={userEmail} userRole={userRole} onLogout={() => { api.auth.logout().finally(() => { setAuthenticated(false); navigate("/login"); }); }} />
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
            <ErrorBoundary key={location.pathname} context={routeName(location.pathname)}>
              <Outlet />
            </ErrorBoundary>
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
