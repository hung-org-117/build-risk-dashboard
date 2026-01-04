"use client";

import { Loader2 } from "lucide-react";

import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

import { StatBox } from "./StatBox";

interface ProcessingCardProps {
    extractedCount: number;
    extractedTotal: number;
    predictedCount: number;
    predictedTotal: number;
    failedExtractionCount: number;
    failedPredictionCount: number;
    status: string;
    lastProcessedBuildId?: number | null;
}

export function ProcessingCard({
    extractedCount,
    extractedTotal,
    predictedCount,
    predictedTotal,
    failedExtractionCount,
    failedPredictionCount,
    status,
    lastProcessedBuildId,
}: ProcessingCardProps) {
    const s = status.toLowerCase();
    const isProcessing = s === "processing";

    return (
        <Card>
            <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-lg flex items-center gap-2">
                            Processing
                            {isProcessing && (
                                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                            )}
                        </CardTitle>
                        <CardDescription>
                            Extract features and predict build risk
                        </CardDescription>
                    </div>
                    {lastProcessedBuildId && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            Last processed:
                            <Badge variant="outline" className="font-mono">
                                #{lastProcessedBuildId}
                            </Badge>
                        </div>
                    )}
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Stats Row */}
                <div className="flex justify-center gap-4">
                    <StatBox
                        label="Extracted"
                        value={`${extractedCount}/${extractedTotal}`}
                        variant={extractedCount === extractedTotal && extractedTotal > 0 ? "success" : "default"}
                    />
                    <StatBox
                        label="Predicted"
                        value={predictedTotal > 0 ? `${predictedCount}/${predictedTotal}` : "—"}
                        variant={predictedCount === predictedTotal && predictedTotal > 0 ? "success" : "default"}
                    />
                    {failedExtractionCount > 0 && (
                        <StatBox
                            label="Extract Failed"
                            value={failedExtractionCount}
                            variant="error"
                        />
                    )}
                    {failedPredictionCount > 0 && (
                        <StatBox
                            label="Predict Failed"
                            value={failedPredictionCount}
                            variant="error"
                        />
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
