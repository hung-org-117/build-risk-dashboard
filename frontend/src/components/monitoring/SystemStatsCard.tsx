"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Activity,
    Database,
    Server,
    Cpu,
    HardDrive,
    Users,
    Zap,
} from "lucide-react";

interface WorkerInfo {
    name: string;
    status: string;
    active_tasks: number;
    reserved_tasks: number;
    pool: number;
}

interface SystemStatsProps {
    celery: {
        workers: WorkerInfo[];
        worker_count: number;
        queues: Record<string, number>;
        status: string;
    };
    redis: {
        connected: boolean;
        version?: string;
        memory_used?: string;
        connected_clients?: number;
        error?: string;
    };
    mongodb: {
        connected: boolean;
        version?: string;
        connections?: { current: number; available: number };
        collections?: number;
        error?: string;
    };
    timestamp: string;
}

interface SystemStatsCardProps {
    stats: SystemStatsProps | null;
    isLoading: boolean;
}

export function SystemStatsCard({ stats, isLoading }: SystemStatsCardProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[1, 2, 3].map((i) => (
                    <Card key={i} className="animate-pulse">
                        <CardHeader className="pb-2">
                            <div className="h-4 bg-muted rounded w-24" />
                        </CardHeader>
                        <CardContent>
                            <div className="h-8 bg-muted rounded w-16 mb-2" />
                            <div className="h-3 bg-muted rounded w-32" />
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    if (!stats) {
        return (
            <Card>
                <CardContent className="pt-6">
                    <p className="text-muted-foreground text-center">
                        Failed to load system stats
                    </p>
                </CardContent>
            </Card>
        );
    }

    const totalQueueMessages = Object.values(stats.celery.queues).reduce(
        (a, b) => a + b,
        0
    );

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Celery Card */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Cpu className="h-4 w-4" />
                        Celery Workers
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-bold">
                            {stats.celery.worker_count}
                        </span>
                        <Badge
                            variant={stats.celery.status === "online" ? "default" : "destructive"}
                        >
                            {stats.celery.status}
                        </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                        {totalQueueMessages} messages in queues
                    </p>
                    {stats.celery.workers.length > 0 && (
                        <div className="mt-3 space-y-1">
                            {stats.celery.workers.map((worker) => (
                                <div
                                    key={worker.name}
                                    className="flex items-center justify-between text-xs"
                                >
                                    <span className="truncate max-w-[120px]" title={worker.name}>
                                        {worker.name.split("@")[1] || worker.name}
                                    </span>
                                    <Badge variant="outline" className="text-xs">
                                        {worker.active_tasks} active
                                    </Badge>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Redis Card */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Zap className="h-4 w-4" />
                        Redis
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-baseline gap-2">
                        <Badge
                            variant={stats.redis.connected ? "default" : "destructive"}
                        >
                            {stats.redis.connected ? "Connected" : "Disconnected"}
                        </Badge>
                    </div>
                    {stats.redis.connected ? (
                        <>
                            <p className="text-xs text-muted-foreground mt-2">
                                Memory: {stats.redis.memory_used}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Clients: {stats.redis.connected_clients}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Version: {stats.redis.version}
                            </p>
                        </>
                    ) : (
                        <p className="text-xs text-destructive mt-2">{stats.redis.error}</p>
                    )}
                </CardContent>
            </Card>

            {/* MongoDB Card */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <Database className="h-4 w-4" />
                        MongoDB
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-baseline gap-2">
                        <Badge
                            variant={stats.mongodb.connected ? "default" : "destructive"}
                        >
                            {stats.mongodb.connected ? "Connected" : "Disconnected"}
                        </Badge>
                    </div>
                    {stats.mongodb.connected ? (
                        <>
                            <p className="text-xs text-muted-foreground mt-2">
                                Collections: {stats.mongodb.collections}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Connections: {stats.mongodb.connections?.current} /{" "}
                                {stats.mongodb.connections?.available}
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Version: {stats.mongodb.version}
                            </p>
                        </>
                    ) : (
                        <p className="text-xs text-destructive mt-2">
                            {stats.mongodb.error}
                        </p>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
