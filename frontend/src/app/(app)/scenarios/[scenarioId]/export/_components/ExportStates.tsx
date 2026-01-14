"use client";

import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Loader2, Clock } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

interface NotReadyStateProps {
    status?: string;
    isProcessing?: boolean;
    buildsExtracted?: number;
    buildsTotal?: number;
}

export function NotReadyState({ status, isProcessing, buildsExtracted = 0, buildsTotal = 0 }: NotReadyStateProps) {
    const progress = buildsTotal > 0 ? Math.round((buildsExtracted / buildsTotal) * 100) : 0;
    
    return (
        <Card>
            <CardHeader>
                <CardTitle>Export Dataset</CardTitle>
                <CardDescription>
                    {isProcessing ? "Feature extraction in progress" : "Complete processing phase first"}
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="p-8 border rounded-lg bg-muted/50 flex flex-col items-center gap-4">
                    {isProcessing ? (
                        <>
                            <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
                            <p className="text-muted-foreground text-center">
                                Extracting features... {buildsExtracted}/{buildsTotal} builds processed
                            </p>
                            <Progress value={progress} className="w-64 h-2" />
                            <p className="text-xs text-muted-foreground">
                                Export will be available once feature extraction completes.
                            </p>
                        </>
                    ) : (
                        <>
                            {status === "ingested" ? (
                                <Clock className="h-12 w-12 text-amber-500" />
                            ) : (
                                <AlertTriangle className="h-12 w-12 text-amber-500" />
                            )}
                            <p className="text-muted-foreground text-center">
                                {status === "ingested" 
                                    ? "Ingestion complete. Start the processing phase to extract features."
                                    : "Dataset export requires the processing phase to be completed."
                                }
                            </p>
                        </>
                    )}
                    <Badge variant="outline" className="text-sm">
                        Current status: {status}
                    </Badge>
                </div>
            </CardContent>
        </Card>
    );
}

export function GeneratingState() {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Generating Dataset</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="p-8 border rounded-lg bg-muted/50 flex flex-col items-center gap-4">
                    <Loader2 className="h-12 w-12 animate-spin text-purple-500" />
                    <p className="text-muted-foreground text-center">
                        Generating train/val/test splits...
                    </p>
                    <p className="text-xs text-muted-foreground">
                        This may take a few minutes depending on the number of builds.
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}

export function LoadingState() {
    return (
        <div className="flex min-h-[400px] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
    );
}
