"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { ReactNode } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileInput, FileOutput, Shield } from "lucide-react";

export default function BuildsLayout({ children }: { children: ReactNode }) {
    const params = useParams<{ scenarioId: string }>();
    const pathname = usePathname();
    const scenarioId = params.scenarioId;

    // Determine active sub-tab
    const getActiveTab = () => {
        if (pathname.includes("/processing")) return "processing";
        return "ingestion";
    };
    const activeTab = getActiveTab();

    const basePath = `/scenarios/${scenarioId}/builds`;

    return (
        <div className="space-y-4">
            {/* Sub-navigation */}
            <Tabs value={activeTab}>
                <TabsList>
                    <TabsTrigger value="ingestion" asChild>
                        <Link href={`${basePath}/ingestion`} className="gap-2">
                            <FileInput className="h-4 w-4" />
                            Ingestion
                        </Link>
                    </TabsTrigger>
                    <TabsTrigger value="processing" asChild>
                        <Link href={`${basePath}/processing`} className="gap-2">
                            <FileOutput className="h-4 w-4" />
                            Processing
                        </Link>
                    </TabsTrigger>
                </TabsList>
            </Tabs>

            {/* Content */}
            {children}
        </div>
    );
}
