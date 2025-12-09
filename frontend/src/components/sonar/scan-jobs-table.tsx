/**
 * Scan Jobs Table - DEPRECATED
 * 
 * This component displayed scan jobs triggered via API.
 * Since scanning is now done via pipeline SonarMeasuresNode,
 * scan jobs are no longer created via API.
 * 
 * Users can view scan results in the scan-metrics-table component.
 */

import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface ScanJobsTableProps {
    repoId: string;
}

export function ScanJobsTable({ repoId }: ScanJobsTableProps) {
    return (
        <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Scan Jobs Deprecated</AlertTitle>
            <AlertDescription>
                SonarQube scanning is now integrated into the feature pipeline.
                When you select sonar_* features during dataset enrichment,
                the pipeline will automatically scan commits and extract metrics.
                <br /><br />
                View scan results in the "Metrics" tab below.
            </AlertDescription>
        </Alert>
    );
}
