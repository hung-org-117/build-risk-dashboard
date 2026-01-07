"use client";

import { useAuth } from "@/contexts/auth-context";

export function useUserPermissions() {
    const { user } = useAuth();

    const role = user?.role ?? "user";
    const isAdmin = role === "admin";

    return {
        // Role checks
        role,
        isAdmin,
        isUser: role === "user",

        // Permission checks (matching backend RBAC)
        canManageRepos: isAdmin,
        canManageDatasets: isAdmin,
        canManageUsers: isAdmin,
        canDeleteData: isAdmin,
        canStartScans: isAdmin,
        canExportData: isAdmin,

        // View permissions (available to all authenticated users)
        canViewDashboard: true,
        canViewRepos: true,
        canViewBuilds: true,
        canViewNotifications: true,
        canManageNotifications: true,
    };
}
