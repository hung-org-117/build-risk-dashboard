"use client";

import { cn } from "@/lib/utils";

interface ResponsiveTableWrapperProps {
    children: React.ReactNode;
    className?: string;
}

/**
 * Wrapper for tables to enable horizontal scroll on tablet/mobile.
 * 
 * Usage:
 * ```tsx
 * <ResponsiveTableWrapper>
 *   <Table>...</Table>
 * </ResponsiveTableWrapper>
 * ```
 */
export function ResponsiveTableWrapper({
    children,
    className,
}: ResponsiveTableWrapperProps) {
    return (
        <div className={cn(
            "w-full overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0",
            className
        )}>
            <div className="min-w-[640px] md:min-w-0">
                {children}
            </div>
        </div>
    );
}
