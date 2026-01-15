import React from "react";
import { Badge } from "@/components/ui/badge";

interface FeatureValueProps {
    value: unknown;
}

export function FeatureValue({ value }: FeatureValueProps) {
    if (value === null || value === undefined) {
        return <span className="text-muted-foreground italic">null</span>;
    }

    if (typeof value === "boolean") {
        return (
            <Badge variant={value ? "default" : "secondary"} className="font-mono">
                {value ? "true" : "false"}
            </Badge>
        );
    }

    if (typeof value === "number") {
        return <span className="font-mono">{value}</span>;
    }

    if (typeof value === "object") {
        const jsonStr = JSON.stringify(value, null, 2);
        return (
            <div className="max-w-[400px] overflow-x-auto">
                <pre className="font-mono text-xs whitespace-pre bg-slate-50 dark:bg-slate-900/50 rounded px-2 py-1">
                    {jsonStr}
                </pre>
            </div>
        );
    }

    const strValue = String(value);

    if (strValue.length > 60 || strValue.includes("#")) {
        return (
            <div className="max-w-[400px] overflow-x-auto">
                <code className="font-mono text-xs whitespace-nowrap bg-slate-50 dark:bg-slate-900/50 rounded px-2 py-1 block">
                    {strValue}
                </code>
            </div>
        );
    }

    return <span className="font-mono">{strValue}</span>;
}
