"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { ArrowLeft, Download, FileSpreadsheet, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const tabs = [
    { id: "ingestion", label: "Ingestion", icon: Download },
    { id: "processing", label: "Processing", icon: Layers },
];

export default function BuildsLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const params = useParams();
    const pathname = usePathname();
    const scenarioId = params.scenarioId as string;

    const currentTab = tabs.find((tab) =>
        pathname.includes(`/builds/${tab.id}`)
    )?.id || "ingestion";

    return (
        <div className="space-y-6">
            {/* Back to scenario */}
            <Button
                variant="ghost"
                asChild
                className="gap-2"
            >
                <Link href={`/ml-scenarios/${scenarioId}`}>
                    <ArrowLeft className="h-4 w-4" />
                    Back to Scenario
                </Link>
            </Button>

            {/* Header */}
            <div className="flex items-center gap-2">
                <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
                <h1 className="text-xl font-semibold">Scenario Builds</h1>
            </div>

            {/* Tab Navigation */}
            <div className="border-b">
                <nav className="flex gap-4" aria-label="Tabs">
                    {tabs.map((tab) => {
                        const Icon = tab.icon;
                        const isActive = currentTab === tab.id;
                        return (
                            <Link
                                key={tab.id}
                                href={`/ml-scenarios/${scenarioId}/builds/${tab.id}`}
                                className={cn(
                                    "flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors",
                                    isActive
                                        ? "border-primary text-primary"
                                        : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground"
                                )}
                            >
                                <Icon className="h-4 w-4" />
                                {tab.label}
                            </Link>
                        );
                    })}
                </nav>
            </div>

            {/* Content */}
            <div>{children}</div>
        </div>
    );
}
