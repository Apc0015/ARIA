import { NavLink } from "react-router-dom";
import { LayoutDashboard, Play, Activity, FileText, Zap, Settings } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", exact: true },
  { to: "/launch", icon: Play, label: "Launch Run", exact: false },
  { to: "/monitor", icon: Activity, label: "Monitor", exact: false },
  { to: "/report", icon: FileText, label: "Reports", exact: false },
  { to: "/sources", icon: Zap, label: "Sources", exact: false },
];

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
              "hover:bg-white/[0.04] hover:text-aria-text2",
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
      <TooltipContent side="right" className="bg-aria-surface border-aria-border text-aria-text2 text-xs">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

export function AppSidebar() {
  return (
    <TooltipProvider>
      <aside className="hidden md:flex w-14 flex-shrink-0 bg-aria-panel border-r border-white/[0.06] flex-col items-center py-3 gap-1">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-aria-brand to-aria-accent flex items-center justify-center text-white text-xs font-[590] mb-3 brand-glow">
          A
        </div>
        {NAV.map((item) => (
          <SidebarItem key={item.to} {...item} />
        ))}
        <div className="flex-1" />
        <SidebarItem to="/settings" icon={Settings} label="Settings" exact={false} />
      </aside>
    </TooltipProvider>
  );
}
