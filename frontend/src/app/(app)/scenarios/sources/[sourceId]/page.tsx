"use client";

import { Loader2, RefreshCw, Trash2, CheckCircle2, XCircle, ArrowLeft } from "lucide-react";
import { useRouter, useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/use-toast";
import { formatDateTime, getBuildSourceStatusConfig, getSourceBuildStatusConfig } from "@/lib/utils";

interface SourceBuild {
    id: string;
    source_id: string;
    build_id_from_source: string;
    repo_name_from_source: string;
    status: "pending" | "found" | "not_found" | "filtered";
    raw_repo_id?: string;
    raw_run_id?: string;
}

interface ValidationStats {
    total: number;
    found: number;
    not_found: number;
    filtered: number;
}

interface BuildSourceDetail {
    id: string;
    name: string;
    description?: string;
    file_name: string;
    rows: number;
    mapped_fields: Record<string, string>;
    validation_status: "pending" | "validating" | "completed" | "failed";
    validation_stats: ValidationStats;
    created_at: string;
    updated_at: string;
}

interface BuildsResponse {
    items: SourceBuild[];
    total: number;
}

const PAGE_SIZE = 20;

function getStatusBadge(status: string) {
    const config = getBuildSourceStatusConfig(status);
    return (
        <Badge variant={config.variant} className={config.className}>
            {config.label}
        </Badge>
    );
}

function getBuildStatusBadge(status: string) {
    const config = getSourceBuildStatusConfig(status);
    
    // Map icon names to actual components
    const iconMap: Record<string, React.ReactNode> = {
        "Found": <CheckCircle2 className="w-4 h-4" />,
        "Not Found": <XCircle className="w-4 h-4" />,
        "Filtered": <XCircle className="w-4 h-4" />,
        "Pending": <Loader2 className="w-4 h-4 animate-spin" />,
    };

    return (
        <div className={`flex items-center gap-2 ${config.color}`}>
            {iconMap[config.label]}
            <span className="text-sm">{config.label}</span>
        </div>
    );
}

export default function SourceDetailPage() {
    const router = useRouter();
    const params = useParams();
    const sourceId = params.sourceId as string;

    const [source, setSource] = useState<BuildSourceDetail | null>(null);
    const [builds, setBuilds] = useState<SourceBuild[]>([]);
    const [loading, setLoading] = useState(true);
    const [buildsLoading, setBuildsLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);

    const loadSourceDetail = useCallback(async () => {
        try {
            const response = await fetch(`/api/build-sources/${sourceId}`);
            if (!response.ok) throw new Error("Failed to load source");

            const data: BuildSourceDetail = await response.json();
            setSource(data);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to load source details",
                variant: "destructive",
            });
            router.push("/scenarios/sources");
        } finally {
            setLoading(false);
        }
    }, [sourceId, router]);

    const loadBuilds = useCallback(
        async (pageNumber = 1) => {
            setBuildsLoading(true);
            try {
                const response = await fetch(
                    `/api/build-sources/${sourceId}/builds?skip=${(pageNumber - 1) * PAGE_SIZE}&limit=${PAGE_SIZE}`
                );
                if (!response.ok) throw new Error("Failed to load builds");

                const data: BuildsResponse = await response.json();
                setBuilds(data.items || []);
                setTotal(data.total);
                setPage(pageNumber);
            } catch (err) {
                console.error(err);
                toast({
                    title: "Error",
                    description: "Failed to load source builds",
                    variant: "destructive",
                });
            } finally {
                setBuildsLoading(false);
            }
        },
        [sourceId]
    );

    const deleteSource = useCallback(async () => {
        setDeleting(true);
        try {
            const response = await fetch(`/api/build-sources/${sourceId}`, {
                method: "DELETE",
            });
            if (!response.ok) throw new Error("Failed to delete source");

            toast({
                title: "Success",
                description: "Build source deleted",
            });
            router.push("/scenarios/sources");
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to delete source",
                variant: "destructive",
            });
        } finally {
            setDeleting(false);
            setDeleteDialogOpen(false);
        }
    }, [sourceId, router]);

    const revalidateSource = useCallback(async () => {
        try {
            const response = await fetch(`/api/build-sources/${sourceId}/validate`, {
                method: "POST",
            });
            if (!response.ok) throw new Error("Failed to revalidate source");

            toast({
                title: "Success",
                description: "Re-validation started",
            });
            loadSourceDetail();
            loadBuilds(1);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to revalidate source",
                variant: "destructive",
            });
        }
    }, [sourceId, loadSourceDetail, loadBuilds]);

    useEffect(() => {
        loadSourceDetail();
    }, [loadSourceDetail]);

    useEffect(() => {
        if (source) {
            loadBuilds();
        }
    }, [source, loadBuilds]);

    const buildColumns: DataTableColumn<SourceBuild>[] = [
        {
            key: "build_id_from_source",
            header: "Build ID",
            render: (item) => (
                <code className="text-xs bg-muted px-2 py-1 rounded font-mono">
                    {item.build_id_from_source}
                </code>
            ),
        },
        {
            key: "repo_name_from_source",
            header: "Repository",
            render: (item) => (
                <span className="font-medium">{item.repo_name_from_source}</span>
            ),
        },
        {
            key: "status",
            header: "Status",
            render: (item) => getBuildStatusBadge(item.status),
        },
        {
            key: "raw_run_id",
            header: "In Warehouse",
            render: (item) =>
                item.raw_run_id ? (
                    <div className="flex items-center gap-2 text-green-600">
                        <CheckCircle2 className="w-4 h-4" />
                        <span className="text-sm">Yes</span>
                    </div>
                ) : (
                    <div className="flex items-center gap-2 text-red-600">
                        <XCircle className="w-4 h-4" />
                        <span className="text-sm">No</span>
                    </div>
                ),
        },
    ];

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-center space-y-4">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
                    <p className="text-muted-foreground">Loading source details...</p>
                </div>
            </div>
        );
    }

    if (!source) {
        return (
            <div className="flex items-center justify-center py-12">
                <Card className="border-red-200">
                    <CardContent className="pt-6">
                        <p className="text-red-600">Source not found</p>
                        <Button
                            variant="outline"
                            className="mt-4"
                            onClick={() => router.push("/scenarios/sources")}
                        >
                            Back to Sources
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const foundPercentage =
        source.rows > 0
            ? ((source.validation_stats.found / source.rows) * 100).toFixed(1)
            : 0;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push("/scenarios/sources")}
                >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back
                </Button>
                <div className="flex-1">
                    <h1 className="text-3xl font-bold">{source.name}</h1>
                    {source.description && (
                        <p className="text-muted-foreground">{source.description}</p>
                    )}
                </div>
                <div className="flex gap-2">
                    {source.validation_status !== "validating" && (
                        <Button
                            variant="outline"
                            onClick={revalidateSource}
                        >
                            <RefreshCw className="w-4 h-4 mr-2" />
                            Re-validate
                        </Button>
                    )}
                    <Button
                        variant="destructive"
                        onClick={() => setDeleteDialogOpen(true)}
                    >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete
                    </Button>
                </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <Card>
                    <CardContent className="pt-6">
                        <p className="text-sm text-muted-foreground">File Name</p>
                        <p className="text-sm font-mono mt-2">{source.file_name}</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <p className="text-sm text-muted-foreground">Total Rows</p>
                        <p className="text-3xl font-bold mt-2">
                            {source.rows.toLocaleString()}
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <p className="text-sm text-muted-foreground">Found</p>
                        <div className="mt-2">
                            <p className="text-3xl font-bold text-green-600">
                                {source.validation_stats.found.toLocaleString()}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {foundPercentage}%
                            </p>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <p className="text-sm text-muted-foreground">Not Found</p>
                        <div className="mt-2">
                            <p className="text-3xl font-bold text-red-600">
                                {source.validation_stats.not_found.toLocaleString()}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {(
                                    ((source.validation_stats.not_found / source.rows) * 100) ||
                                    0
                                ).toFixed(1)}
                                %
                            </p>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <p className="text-sm text-muted-foreground">Status</p>
                        <div className="mt-2">{getStatusBadge(source.validation_status)}</div>
                    </CardContent>
                </Card>
            </div>

            {/* Metadata */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                    <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Uploaded:</span>
                        <span className="text-sm font-medium">
                            {formatDateTime(source.created_at)}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Last Updated:</span>
                        <span className="text-sm font-medium">
                            {formatDateTime(source.updated_at)}
                        </span>
                    </div>
                    {Object.keys(source.mapped_fields).length > 0 && (
                        <div className="mt-4">
                            <span className="text-sm text-muted-foreground block mb-2">
                                Mapped Fields:
                            </span>
                            <div className="space-y-1">
                                {Object.entries(source.mapped_fields).map(([csv, field]) => (
                                    <div key={csv} className="font-mono text-xs">
                                        <code className="bg-muted px-2 py-1 rounded">
                                            {csv}
                                        </code>
                                        <span className="text-muted-foreground mx-2">→</span>
                                        <code className="bg-muted px-2 py-1 rounded">
                                            {field}
                                        </code>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Validated Builds Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Validated Builds</CardTitle>
                    <CardDescription>
                        {builds.length > 0
                            ? `Showing ${builds.length} of ${total} builds`
                            : "No builds to display"}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {buildsLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="w-5 h-5 animate-spin mr-2 text-muted-foreground" />
                            <p className="text-muted-foreground">Loading builds...</p>
                        </div>
                    ) : builds.length === 0 ? (
                        <div className="flex items-center justify-center py-8">
                            <p className="text-muted-foreground">No validated builds</p>
                        </div>
                    ) : (
                        <DataTable
                        columns={buildColumns}
                        data={builds}
                        total={total}
                        page={page}
                        pageSize={PAGE_SIZE}
                        onPageChange={loadBuilds}
                        rowKey={(item) => item.id}
                    />
                    )}
                </CardContent>
            </Card>

            {/* Delete Confirmation Dialog */}
            <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <DialogContent>
                    <DialogTitle>Delete Build Source</DialogTitle>
                    <DialogDescription>
                        Are you sure you want to delete &quot;{source.name}&quot;? This action cannot be
                        undone.
                    </DialogDescription>
                    <div className="flex gap-2 justify-end mt-6">
                        <Button
                            variant="outline"
                            onClick={() => setDeleteDialogOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={deleteSource}
                            disabled={deleting}
                        >
                            {deleting ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Deleting...
                                </>
                            ) : (
                                "Delete"
                            )}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
