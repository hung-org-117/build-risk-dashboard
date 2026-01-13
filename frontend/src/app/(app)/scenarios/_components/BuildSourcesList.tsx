"use client";

import {
    Database,
    MoreVertical,
    Trash2,
    Eye,
    RefreshCw,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api/client";

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

export function BuildSourcesList() {
    const router = useRouter();
    const [sources, setSources] = useState<BuildSourceRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    const [stats, setStats] = useState({
        totalSources: 0,
        totalBuilds: 0,
    });

    const loadSources = useCallback(async (pageNumber = 1) => {
        setLoading(true);
        try {
            const response = await api.get<ListResponse>("/build-sources", {
                params: {
                    skip: (pageNumber - 1) * PAGE_SIZE,
                    limit: PAGE_SIZE,
                },
            });

            const data = response.data;
            setSources(data.items || []);
            setTotal(data.total);
            setPage(pageNumber);

            // Calculate stats
            if (data.items && data.items.length > 0) {
                const aggregated = data.items.reduce(
                    (acc, source) => ({
                        totalBuilds: acc.totalBuilds + source.rows,
                    }),
                    { totalBuilds: 0 }
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
            await api.delete(`/build-sources/${sourceId}`);

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
            await api.post(`/build-sources/${sourceId}/validate`);

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
                            onClick={(e) => {
                                e.stopPropagation();
                                deleteSource(item.id);
                            }}
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
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                            {/* NOTE: The 'Upload First Source' button below is optional if the parent page handles it, 
                                but good to keep as a fallback or explicit call to action here. 
                                It uses the same route as the parent button. */}
                            <Button onClick={() => router.push("/scenarios/upload")}>
                                <div className="flex items-center">
                                    {/* Plus icon is imported but previously was used with w-4 h-4 mr-2 */}
                                    {/* Re-using the same icon setup as original file */}
                                    <svg
                                        xmlns="http://www.w3.org/2000/svg"
                                        width="16"
                                        height="16"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        className="w-4 h-4 mr-2"
                                    >
                                        <path d="M5 12h14"></path>
                                        <path d="M12 5v14"></path>
                                    </svg>
                                    Upload First Source
                                </div>
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
                            onRowClick={(item) => router.push(`/scenarios/sources/${item.id}`)}
                            rowKey={(item) => item.id}
                        />
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
