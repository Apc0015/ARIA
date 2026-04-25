import { NavLink } from "react-router-dom";
import { LayoutDashboard, Play, Activity, FileText, Zap, Settings, Sun, Moon } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", exact: true },
  { to: "/launch", icon: Play, label: "Launch Run", exact: false },
  { to: "/sources", icon: Zap, label: "Sources", exact: false },
  { to: "/report", icon: FileText, label: "Reports", exact: false },
  { to: "/monitor", icon: Activity, label: "Monitor", exact: false },
];

const ALL_NAV = [...NAV, { to: "/settings", icon: Settings, label: "Settings", exact: false }];

interface AppSidebarProps {
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

function SidebarItem({ to, icon: Icon, label, exact }: typeof NAV[0]) {
  return (
    <Tooltip delayDuration={300}>
      <TooltipTrigger asChild>
        <NavLink
          to={to}
          end={exact}
          className={({ isActive }) =>
            cn(
              "relative w-9 h-9 rounded-lg flex items-center justify-center",
              "text-aria-text4 transition-all duration-150",
              "hover:bg-black/[0.04] dark:hover:bg-white/[0.04] hover:text-aria-text2",
              isActive && "bg-aria-accent/[0.15] text-aria-accent"
            )
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span className="absolute -left-px top-[25%] bottom-[25%] w-0.5 rounded-r bg-aria-accent" />
              )}
              <Icon size={16} />
            </>
          )}
        </NavLink>
      </TooltipTrigger>
      <TooltipContent side="right" className="bg-aria-surface border border-[var(--aria-border)] text-aria-text2 text-xs">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

export function AppSidebar({ theme, onToggleTheme }: AppSidebarProps) {
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const themeLabel = theme === "dark" ? "Switch to Light" : "Switch to Dark";

  return (
    <>
      {/* Desktop sidebar */}
      <TooltipProvider>
        <aside className="hidden md:flex w-14 flex-shrink-0 bg-aria-panel border-r border-[var(--aria-border)] flex-col items-center py-3 gap-1">
          {/* Logo */}
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-aria-brand to-aria-accent flex items-center justify-center text-white text-xs font-[590] mb-3 brand-glow">
            A
          </div>

          {NAV.map((item) => (
            <SidebarItem key={item.to} {...item} />
          ))}

          <div className="flex-1" />

          {/* Theme toggle */}
          <Tooltip delayDuration={300}>
            <TooltipTrigger asChild>
              <button
                onClick={onToggleTheme}
                className={cn(
                  "w-9 h-9 rounded-lg flex items-center justify-center",
                  "text-aria-text4 transition-all duration-150",
                  "hover:bg-black/[0.04] dark:hover:bg-white/[0.04] hover:text-aria-text2"
                )}
              >
                <ThemeIcon size={16} />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="bg-aria-surface border border-[var(--aria-border)] text-aria-text2 text-xs">
              {themeLabel}
            </TooltipContent>
          </Tooltip>

          <SidebarItem to="/settings" icon={Settings} label="Settings" exact={false} />
        </aside>
      </TooltipProvider>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-aria-panel border-t border-[var(--aria-border)] flex items-center justify-around px-2 z-50">
        {ALL_NAV.map(({ to, icon: Icon, label, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors",
                isActive ? "text-aria-accent" : "text-aria-text4"
              )
            }
          >
            <Icon size={18} />
            <span className="text-[9px] font-[510]">{label}</span>
          </NavLink>
        ))}
        {/* Theme toggle in mobile bar */}
        <button
          onClick={onToggleTheme}
          className="flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors text-aria-text4"
        >
          <ThemeIcon size={18} />
          <span className="text-[9px] font-[510]">Theme</span>
        </button>
      </nav>
    </>
  );
}
