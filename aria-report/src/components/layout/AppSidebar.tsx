import { NavLink } from "react-router-dom";
import { LayoutDashboard, Play, Activity, FileText, Zap, Settings, Sun, Moon } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/",        icon: LayoutDashboard, label: "Dashboard",  exact: true  },
  { to: "/launch",  icon: Play,            label: "Launch Run", exact: false },
  { to: "/sources", icon: Zap,             label: "Sources",    exact: false },
  { to: "/report",  icon: FileText,        label: "Reports",    exact: false },
  { to: "/monitor", icon: Activity,        label: "Monitor",    exact: false },
];

const ALL_NAV = [...NAV, { to: "/settings", icon: Settings, label: "Settings", exact: false }];

interface AppSidebarProps {
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

function SidebarItem({ to, icon: Icon, label, exact }: typeof NAV[0]) {
  return (
    <Tooltip delayDuration={400}>
      <TooltipTrigger asChild>
        <NavLink
          to={to}
          end={exact}
          className={({ isActive }) =>
            cn(
              "relative w-9 h-9 rounded-[6px] flex items-center justify-center",
              "transition-all duration-100",
              isActive
                ? "sidebar-active text-aria-accent"
                : "text-aria-text4 hover:text-aria-text2 hover:bg-[rgba(255,255,255,0.03)] dark:hover:bg-[rgba(255,255,255,0.03)]"
            )
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span className="absolute -left-px top-[24%] bottom-[24%] w-[2px] rounded-r-full bg-aria-accent opacity-90" />
              )}
              <Icon size={15} strokeWidth={isActive ? 2 : 1.75} />
            </>
          )}
        </NavLink>
      </TooltipTrigger>
      <TooltipContent
        side="right"
        sideOffset={6}
        className="bg-aria-surface border border-[var(--aria-border)] text-aria-text2 text-[12px] font-[510] px-2.5 py-1 shadow-[rgba(0,0,0,0.2)_0px_4px_8px]"
      >
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

export function AppSidebar({ theme, onToggleTheme }: AppSidebarProps) {
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const themeLabel = theme === "dark" ? "Light mode" : "Dark mode";

  return (
    <>
      {/* Desktop sidebar */}
      <TooltipProvider>
        <aside className="hidden md:flex w-14 flex-shrink-0 bg-aria-panel border-r border-[var(--aria-border-subtle)] flex-col items-center py-3 gap-0.5">
          {/* Logomark */}
          <div className="w-7 h-7 rounded-[6px] bg-gradient-to-br from-aria-brand to-aria-accent flex items-center justify-center text-white text-[12px] font-[620] mb-4 select-none brand-glow">
            A
          </div>

          {NAV.map((item) => (
            <SidebarItem key={item.to} {...item} />
          ))}

          <div className="flex-1" />

          {/* Theme toggle */}
          <Tooltip delayDuration={400}>
            <TooltipTrigger asChild>
              <button
                onClick={onToggleTheme}
                className="w-9 h-9 rounded-[6px] flex items-center justify-center text-aria-text4 hover:text-aria-text2 hover:bg-[rgba(255,255,255,0.03)] transition-all duration-100"
              >
                <ThemeIcon size={14} strokeWidth={1.75} />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={6} className="bg-aria-surface border border-[var(--aria-border)] text-aria-text2 text-[12px] font-[510] px-2.5 py-1">
              {themeLabel}
            </TooltipContent>
          </Tooltip>

          <SidebarItem to="/settings" icon={Settings} label="Settings" exact={false} />
        </aside>
      </TooltipProvider>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 h-14 bg-aria-panel border-t border-[var(--aria-border-subtle)] flex items-center justify-around px-1">
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
            <Icon size={17} strokeWidth={1.75} />
            <span className="text-[9px] font-[510]">{label}</span>
          </NavLink>
        ))}
        <button
          onClick={onToggleTheme}
          className="flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg text-aria-text4 hover:text-aria-text2 transition-colors"
        >
          <ThemeIcon size={17} strokeWidth={1.75} />
          <span className="text-[9px] font-[510]">Theme</span>
        </button>
      </nav>
    </>
  );
}
