"use client";

import { useEffect } from "react";
import { registerErrorToastHandler } from "@/lib/api/client";
import { toast } from "@/components/ui/use-toast";

/**
 * Provider that registers the global API error toast handler.
 * Place this inside the root layout to enable automatic error toasts.
 */
export function ApiErrorToastProvider({ children }: { children: React.ReactNode }) {
    useEffect(() => {
        // Register the toast handler for API errors
        registerErrorToastHandler((title, description) => {
            toast({
                title,
                description,
                variant: "destructive",
            });
        });
    }, []);

    return <>{children}</>;
}
