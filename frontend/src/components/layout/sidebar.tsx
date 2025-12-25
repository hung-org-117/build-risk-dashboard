"use client";

import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";
import { Activity, BadgeCheck, Database, GitBranch, Home, Settings, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navigation = [
  {
    label: "Overview",
    href: "/overview",
    icon: Home,
    adminOnly: false,
    guestOnly: false,
    userOnly: false, // Shown to all
  },
  {
    label: "My Repositories",
    href: "/my-repos",
    icon: GitBranch,
    adminOnly: false,
    guestOnly: false,
    userOnly: true, // Only for org members
  },
  {
    label: "Projects",
    href: "/projects",
    icon: Database,
    adminOnly: false,
    guestOnly: true, // Admin + Guest
    userOnly: false,
  },
  {
    label: "Repositories",
    href: "/repositories",
    icon: BadgeCheck,
    adminOnly: true, // Admin only
    guestOnly: false,
    userOnly: false,
  },
  {
    label: "Monitoring",
    href: "/admin/monitoring",
    icon: Activity,
    adminOnly: true, // Admin only
    guestOnly: false,
    userOnly: false,
  },
  {
    label: "Users",
    href: "/admin/users",
    icon: Users,
    adminOnly: true, // Admin only
    guestOnly: false,
    userOnly: false,
  },
  {
    label: "App Settings",
    href: "/admin/settings",
    icon: Settings,
    adminOnly: true, // Admin only
    guestOnly: false,
    userOnly: false,
  },
];

interface SidebarProps {
  collapsed?: boolean;
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  const pathname = usePathname();
  const { user } = useAuth();

  const isAdmin = user?.role === "admin";
  const isGuest = user?.role === "guest";

  const visibleNavigation = navigation.filter((item) => {
    // Admin sees everything except userOnly
    if (isAdmin) return !item.userOnly;
    // Guest sees guestOnly and common pages, not adminOnly or userOnly
    if (isGuest) return item.guestOnly || (!item.adminOnly && !item.userOnly);
    // User (org member) sees userOnly and common pages
    return item.userOnly || (!item.adminOnly && !item.guestOnly);
  });

  return (
    <TooltipProvider delayDuration={0}>
      <div className="flex h-full flex-col border-r bg-white/70 backdrop-blur dark:bg-slate-950/90">
        <div className={cn(
          "flex h-16 items-center gap-2 border-b",
          collapsed ? "justify-center px-2" : "px-6"
        )}>
          <div>
            <p className={cn(
              "font-semibold",
              collapsed ? "text-sm" : "text-lg"
            )}>
              {collapsed ? "BG" : "BuildGuard"}
            </p>
          </div>
        </div>

        <nav className={cn(
          "flex-1 space-y-1 py-4",
          collapsed ? "px-2" : "px-3"
        )}>
          {visibleNavigation.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;

            const linkContent = (
              <Link
                href={item.href}
                className={cn(
                  "group flex items-center rounded-lg text-sm font-medium transition-colors",
                  collapsed ? "justify-center p-2" : "gap-3 px-3 py-2",
                  isActive ? "bg-blue-600 text-white hover:text-white" : ""
                )}
              >
                <Icon
                  className={cn(
                    collapsed ? "h-5 w-5" : "h-4 w-4",
                    isActive ? "text-white" : "text-muted-foreground"
                  )}
                />
                {!collapsed && <span className="flex-1">{item.label}</span>}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>
                    {linkContent}
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return <div key={item.href}>{linkContent}</div>;
          })}
        </nav>
      </div>
    </TooltipProvider>
  );
}


