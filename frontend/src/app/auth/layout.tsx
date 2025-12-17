import type { ReactNode } from "react";

/**
 * Auth layout - standalone, no authentication checks.
 * 
 * This layout is used for auth-related pages that should be accessible
 * without authentication (like error pages, logout confirmation, etc.)
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
    return <>{children}</>;
}
