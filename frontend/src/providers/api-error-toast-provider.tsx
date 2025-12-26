"use client";

import { useEffect } from "react";
import { registerErrorToastHandler } from "@/lib/api/client";
import { toast } from "@/components/ui/use-toast";

export function ApiErrorToastProvider({ children }: { children: React.ReactNode }) {
    useEffect(() => {
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
