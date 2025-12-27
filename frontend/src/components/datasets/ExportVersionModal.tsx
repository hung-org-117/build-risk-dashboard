"use client";

import { ExportModal, type ExportAdapter } from "@/components/common/ExportModal";
import { datasetVersionApi } from "@/lib/api";

interface ExportVersionModalProps {
    isOpen: boolean;
    onClose: () => void;
    datasetId: string;
    versionId: string;
    versionName: string;
    totalRows: number;
}

/**
 * Export modal specifically for Dataset Versions.
 * Uses the generic ExportModal with a dataset version adapter.
 */
export function ExportVersionModal({
    isOpen,
    onClose,
    datasetId,
    versionId,
    versionName,
    totalRows,
}: ExportVersionModalProps) {
    // Create adapter for dataset version export
    const adapter: ExportAdapter = {
        name: versionName,
        totalRows,
        downloadStream: (format) =>
            datasetVersionApi.downloadExport(datasetId, versionId, format),
        createAsyncJob: (format) =>
            datasetVersionApi.createExportJob(datasetId, versionId, format),
        getJobStatus: (jobId) =>
            datasetVersionApi.getExportJobStatus(datasetId, jobId),
        downloadJob: (jobId) =>
            datasetVersionApi.downloadExportJob(datasetId, jobId),
    };

    return <ExportModal isOpen={isOpen} onClose={onClose} adapter={adapter} />;
}
