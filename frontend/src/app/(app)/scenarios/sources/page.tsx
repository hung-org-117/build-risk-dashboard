"use client";

import {
    Database,
    Plus,
    MoreVertical,
    Trash2,
    Eye,
    RefreshCw,
} from "lucide-react";
import { useRouter } from "next/navigation";
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
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "@/components/ui/use-toast";
import { formatDateTime, getBuildSourceStatusConfig } from "@/lib/utils";

interface BuildSourceRecord {
    id: string;
    name: string;
    description?: string;
    file_name: string;
    rows: number;
    validation_status: "pending" | "validating" | "completed" | "failed";
    validation_stats: {
        total: number;
        found: number;
        not_found: number;
        filtered: number;
    };
    created_at: string;
    updated_at: string;
}

interface ListResponse {
    items: BuildSourceRecord[];
    total: number;
    skip: number;
    limit: number;
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

export default function BuildSourcesPage() {
    const router = useRouter();
    const [sources, setSources] = useState<BuildSourceRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    const [stats, setStats] = useState({
        totalSources: 0,
        totalBuilds: 0,
        found: 0,
        notFound: 0,
    });

    const loadSources = useCallback(async (pageNumber = 1) => {
        setLoading(true);
        try {
            const response = await fetch(
                `/api/build-sources?skip=${(pageNumber - 1) * PAGE_SIZE}&limit=${PAGE_SIZE}`
            );
            if (!response.ok) throw new Error("Failed to load sources");

            const data: ListResponse = await response.json();
            setSources(data.items || []);
            setTotal(data.total);
            setPage(pageNumber);

            // Calculate stats
            if (data.items && data.items.length > 0) {
                const aggregated = data.items.reduce(
                    (acc, source) => ({
                        totalBuilds: acc.totalBuilds + source.rows,
                        found: acc.found + source.validation_stats.found,
                        notFound: acc.notFound + source.validation_stats.not_found,
                    }),
                    { totalBuilds: 0, found: 0, notFound: 0 }
                );
                setStats({
                    totalSources: data.total,
                    ...aggregated,
                });
            }
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to load build sources",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    }, []);

    const deleteSource = useCallback(async (sourceId: string) => {
        if (!window.confirm("Are you sure you want to delete this source?")) return;

        try {
            const response = await fetch(`/api/build-sources/${sourceId}`, {
                method: "DELETE",
            });
            if (!response.ok) throw new Error("Failed to delete source");

            toast({
                title: "Success",
                description: "Build source deleted",
            });
            loadSources(page);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to delete source",
                variant: "destructive",
            });
        }
    }, [page, loadSources]);

    const revalidateSource = useCallback(async (sourceId: string) => {
        try {
            const response = await fetch(`/api/build-sources/${sourceId}/validate`, {
                method: "POST",
            });
            if (!response.ok) throw new Error("Failed to revalidate source");

            toast({
                title: "Success",
                description: "Re-validation started",
            });
            loadSources(page);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to revalidate source",
                variant: "destructive",
            });
        }
    }, [page, loadSources]);

    useEffect(() => {
        loadSources();
    }, [loadSources]);

    const columns: DataTableColumn<BuildSourceRecord>[] = [
        {
            key: "name",
            header: "Name",
            render: (item) => (
                <button
                    onClick={() => router.push(`/scenarios/sources/${item.id}`)}
                    className="font-medium hover:underline text-blue-600"
                >
                    {item.name}
                </button>
            ),
        },
        {
            key: "file_name",
            header: "File",
            render: (item) => (
                <code className="text-xs bg-muted px-2 py-1 rounded">{item.file_name}</code>
            ),
        },
        {
            key: "rows",
            header: "Rows",
            render: (item) => (
                <span className="font-medium">{item.rows.toLocaleString()}</span>
            ),
        },
        {
            key: "validation_status",
            header: "Status",
            render: (item) => getStatusBadge(item.validation_status),
        },
        {
            key: "validation_stats",
            header: "Results",
            render: (item) => (
                <div className="text-sm">
                    <span className="text-green-600 font-semibold">
                        {item.validation_stats.found}
                    </span>
                    <span className="text-muted-foreground"> / </span>
                    <span className="text-red-600 font-semibold">
                        {item.validation_stats.not_found}
                    </span>
                    <span className="text-muted-foreground"> found/not found</span>
                </div>
            ),
        },
        {
            key: "created_at",
            header: "Uploaded",
            render: (item) => (
                <span className="text-sm text-muted-foreground">
                    {formatDateTime(item.created_at)}
                </span>
            ),
        },
        {
            key: "actions",
            header: "",
            render: (item) => (
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                            <MoreVertical className="w-4 h-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        <DropdownMenuItem
                            onClick={() => router.push(`/scenarios/sources/${item.id}`)}
                        >
                            <Eye className="w-4 h-4 mr-2" />
                            View Details
                        </DropdownMenuItem>
                        {item.validation_status !== "validating" && (
                            <DropdownMenuItem onClick={() => revalidateSource(item.id)}>
                                <RefreshCw className="w-4 h-4 mr-2" />
                                Re-validate
                            </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                            onClick={() => deleteSource(item.id)}
                            className="text-red-600"
                        >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            ),
        },
    ];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold">Build Sources</h1>
                    <p className="text-muted-foreground">
                        Manage uploaded CSV files with validated builds
                    </p>
                </div>
                <Button onClick={() => router.push("/scenarios/upload")}>
                    <Plus className="w-4 h-4 mr-2" />
                    Upload New Source
                </Button>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">Total Sources</p>
                                <p className="text-2xl font-bold">{stats.totalSources}</p>
                            </div>
                            <Database className="w-8 h-8 text-muted-foreground opacity-50" />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">Total Builds</p>
                                <p className="text-2xl font-bold">
                                    {stats.totalBuilds.toLocaleString()}
                                </p>
                            </div>
                            <Database className="w-8 h-8 text-blue-500 opacity-50" />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">Found</p>
                                <p className="text-2xl font-bold text-green-600">
                                    {stats.found.toLocaleString()}
                                </p>
                            </div>
                            <Database className="w-8 h-8 text-green-500 opacity-50" />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">Not Found</p>
                                <p className="text-2xl font-bold text-red-600">
                                    {stats.notFound.toLocaleString()}
                                </p>
                            </div>
                            <Database className="w-8 h-8 text-red-500 opacity-50" />
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Sources Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Build Sources</CardTitle>
                    <CardDescription>
                        {sources.length > 0
                            ? `Showing ${sources.length} of ${total} sources`
                            : "No build sources uploaded yet"}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <div className="text-muted-foreground">Loading sources...</div>
                        </div>
                    ) : sources.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-8">
                            <Database className="w-12 h-12 text-muted-foreground opacity-50 mb-4" />
                            <p className="text-muted-foreground mb-4">No build sources yet</p>
                            <Button onClick={() => router.push("/scenarios/upload")}>
                                <Plus className="w-4 h-4 mr-2" />
                                Upload First Source
                            </Button>
                        </div>
                    ) : (
                        <DataTable
                        columns={columns}
                        data={sources}
                        total={total}
                        page={page}
                        pageSize={PAGE_SIZE}
                        onPageChange={loadSources}
                        rowKey={(item) => item.id}
                    />
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
