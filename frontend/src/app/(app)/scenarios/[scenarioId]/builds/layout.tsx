"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export default function BuildsLayout({ children }: { children: ReactNode }) {
    const params = useParams<{ scenarioId: string }>();
    const pathname = usePathname();
    const scenarioId = params.scenarioId;

    // Determine active sub-tab
    const getActiveTab = () => {
        if (pathname.endsWith("/processing")) return "processing";
        if (pathname.endsWith("/scans")) return "scans";
        return "ingestion";
    };
    const activeTab = getActiveTab();

    const basePath = `/scenarios/${scenarioId}/builds`;

    const TabButton = ({ tab, label, href }: {
        tab: string;
        label: string;
        href: string
    }) => {
        const isActive = activeTab === tab;
        return (
            <Link
                href={href}
                className={cn(
                    "px-3 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-2",
                    isActive
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                )}
            >
                {label}
            </Link>
        );
    };

    return (
        <div className="space-y-4">
            {/* Sub-tabs Navigation */}
            <div className="flex items-center justify-between">
                <div className="flex gap-1 rounded-lg bg-muted p-1">
                    <TabButton tab="ingestion" label="Data Collection" href={`${basePath}/ingestion`} />
                    <TabButton
                        tab="processing"
                        label="Feature Extraction"
                        href={`${basePath}/processing`}
                    />
                    <TabButton
                        tab="scans"
                        label="Integration Scans"
                        href={`${basePath}/scans`}
                    />
                </div>
            </div>

            {/* Page Content */}
            {children}
        </div>
    );
}

