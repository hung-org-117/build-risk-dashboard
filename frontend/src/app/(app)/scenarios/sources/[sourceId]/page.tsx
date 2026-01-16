"use client";

import { Loader2, Trash2, CheckCircle2, XCircle, ArrowLeft } from "lucide-react";
import { useRouter, useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api/client";
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
import { SourceValidationStats } from "@/types";

interface SourceBuild {
    id: string;
    source_id: string;
    build_id_from_source: string;
    repo_name_from_source: string;
    status: "pending" | "found" | "not_found" | "filtered";
    raw_repo_id?: string;
    raw_run_id?: string;
    commit_sha?: string;
    web_url?: string;
}

interface BuildSourceDetail {
    id: string;
    name: string;
    description?: string;
    file_name: string;
    rows: number;
    mapped_fields: Record<string, string>;
    validation_status: "pending" | "validating" | "completed" | "failed";
    validation_stats: SourceValidationStats;
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
            const response = await api.get<BuildSourceDetail>(`/build-sources/${sourceId}`);
            setSource(response.data);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to load source details",
                variant: "destructive",
            });
            router.push("/scenarios?tab=sources");
        } finally {
            setLoading(false);
        }
    }, [sourceId, router]);

    const loadBuilds = useCallback(
        async (pageNumber = 1) => {
            setBuildsLoading(true);
            try {
                const response = await api.get<BuildsResponse>(
                    `/build-sources/${sourceId}/builds`,
                    {
                        params: {
                            skip: (pageNumber - 1) * PAGE_SIZE,
                            limit: PAGE_SIZE,
                        },
                    }
                );
                const data = response.data;
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
            await api.delete(`/build-sources/${sourceId}`);

            toast({
                title: "Success",
                description: "Build source deleted",
            });
            router.push("/scenarios?tab=sources");
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
            key: "commit_sha",
            header: "Commit",
            render: (item) =>
                item.commit_sha ? (
                    <code className="text-xs font-mono text-muted-foreground">
                        {item.commit_sha.substring(0, 8)}
                    </code>
                ) : (
                    <span className="text-muted-foreground text-sm">—</span>
                ),
        },
        {
            key: "web_url",
            header: "CI Link",
            render: (item) =>
                item.web_url ? (
                    <a
                        href={item.web_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-sm"
                        onClick={(e) => e.stopPropagation()}
                    >
                        View Build
                    </a>
                ) : (
                    <span className="text-muted-foreground text-sm">—</span>
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
                            onClick={() => router.push("/scenarios?tab=sources")}
                        >
                            Back to Sources
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => router.push("/scenarios?tab=sources")}
                >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back
                </Button>
                <div className="flex-1">
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold">{source.name}</h1>
                        {getStatusBadge(source.validation_status)}
                    </div>
                    {source.description && (
                        <p className="text-muted-foreground mt-1">{source.description}</p>
                    )}
                </div>
                <div className="flex gap-2">
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => setDeleteDialogOpen(true)}
                    >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete
                    </Button>
                </div>
            </div>

            {/* Main Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Configuration
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div>
                            <span className="text-sm text-muted-foreground block">File Name</span>
                            <span className="font-mono text-sm">{source.file_name}</span>
                        </div>
                        <div className="flex gap-8">
                            <div>
                                <span className="text-sm text-muted-foreground block">Uploaded</span>
                                <span className="text-sm font-medium">{formatDateTime(source.created_at)}</span>
                            </div>
                            <div>
                                <span className="text-sm text-muted-foreground block">Last Updated</span>
                                <span className="text-sm font-medium">{formatDateTime(source.updated_at)}</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Data Summary
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-baseline gap-2">
                            <span className="text-4xl font-bold">
                                {source.rows?.toLocaleString() ?? 0}
                            </span>
                            <span className="text-muted-foreground">total rows</span>
                        </div>

                        {Object.keys(source.mapped_fields).length > 0 && (
                            <div className="mt-4 pt-4 border-t">
                                <span className="text-xs text-muted-foreground block mb-2">
                                    Mapped Fields
                                </span>
                                <div className="flex flex-wrap gap-2">
                                    {Object.entries(source.mapped_fields).map(([csv, field]) => (
                                        <div key={csv} className="font-mono text-xs bg-muted px-2 py-1 rounded border">
                                            {csv} <span className="text-muted-foreground">→</span> {field}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Validated Builds Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Validated Builds</CardTitle>
                    <CardDescription>
                        {builds.length > 0
                            ? `Showing ${builds.length} of ${total} records`
                            : "No data available"}
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
