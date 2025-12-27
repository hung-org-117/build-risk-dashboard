"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    ResponsiveContainer,
    Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart3, Hash, Type, ToggleLeft } from "lucide-react";
import {
    statisticsApi,
    type NumericDistribution,
    type CategoricalDistribution,
} from "@/lib/api/statistics";

interface FeatureDistributionCarouselProps {
    datasetId: string;
    versionId: string;
    features: string[];
}

interface FeatureCardData {
    feature: string;
    loaded: boolean;
    loading: boolean;
    error: boolean;
    distribution: NumericDistribution | CategoricalDistribution | null;
}

const COLORS = [
    "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe",
    "#2563eb", "#1d4ed8", "#1e40af", "#1e3a8a", "#172554",
];

function getDataTypeIcon(dataType: string) {
    switch (dataType) {
        case "integer":
        case "float":
        case "numeric":
            return <Hash className="h-3 w-3" />;
        case "boolean":
            return <ToggleLeft className="h-3 w-3" />;
        default:
            return <Type className="h-3 w-3" />;
    }
}

function FeatureCard({
    feature,
    datasetId,
    versionId,
    onVisible,
}: {
    feature: string;
    datasetId: string;
    versionId: string;
    onVisible: (feature: string) => void;
}) {
    const cardRef = useRef<HTMLDivElement>(null);
    const [data, setData] = useState<FeatureCardData>({
        feature,
        loaded: false,
        loading: false,
        error: false,
        distribution: null,
    });

    // IntersectionObserver for lazy loading
    useEffect(() => {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting && !data.loaded && !data.loading) {
                        onVisible(feature);
                        loadDistribution();
                    }
                });
            },
            { threshold: 0.1, rootMargin: "100px" }
        );

        if (cardRef.current) {
            observer.observe(cardRef.current);
        }

        return () => observer.disconnect();
    }, [feature, data.loaded, data.loading, onVisible]);

    const loadDistribution = useCallback(async () => {
        setData((prev) => ({ ...prev, loading: true }));
        try {
            const response = await statisticsApi.getDistributions(datasetId, versionId, {
                features: [feature],
                bins: 10,
                top_n: 8,
            });
            const dist = response.distributions[feature];
            setData({
                feature,
                loaded: true,
                loading: false,
                error: false,
                distribution: dist || null,
            });
        } catch {
            setData((prev) => ({ ...prev, loading: false, error: true, loaded: true }));
        }
    }, [datasetId, versionId, feature]);

    // Render mini chart
    const renderMiniChart = () => {
        if (data.loading) {
            return (
                <div className="h-24 flex items-center justify-center">
                    <Skeleton className="h-20 w-full" />
                </div>
            );
        }

        if (data.error || !data.distribution) {
            return (
                <div className="h-24 flex items-center justify-center text-muted-foreground text-xs">
                    No data
                </div>
            );
        }

        const dist = data.distribution;
        const isNumeric = dist.data_type === "integer" || dist.data_type === "float" || dist.data_type === "numeric";

        if (isNumeric) {
            const numDist = dist as NumericDistribution;
            const chartData = numDist.bins.map((bin, idx) => ({
                name: idx.toString(),
                count: bin.count,
            }));

            return (
                <ResponsiveContainer width="100%" height={80}>
                    <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                        <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                            {chartData.map((_, idx) => (
                                <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            );
        } else {
            // Categorical - horizontal bars
            const catDist = dist as CategoricalDistribution;
            const chartData = catDist.values.slice(0, 5).map((v) => ({
                name: v.value.length > 12 ? v.value.slice(0, 12) + "..." : v.value,
                count: v.count,
            }));

            return (
                <ResponsiveContainer width="100%" height={80}>
                    <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 5, left: 35, bottom: 5 }}>
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} width={30} />
                        <Bar dataKey="count" radius={[0, 2, 2, 0]}>
                            {chartData.map((_, idx) => (
                                <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            );
        }
    };

    const dist = data.distribution;
    const dataType = dist?.data_type || "unknown";
    const isNumeric = dataType === "integer" || dataType === "float" || dataType === "numeric";

    // Stats summary
    const getStatsSummary = () => {
        if (!dist) return null;

        if (isNumeric) {
            const numDist = dist as NumericDistribution;
            if (!numDist.stats) return null;
            return (
                <div className="text-xs text-muted-foreground space-y-0.5">
                    <div>μ = {numDist.stats.mean.toFixed(2)}</div>
                    <div>σ = {numDist.stats.std.toFixed(2)}</div>
                </div>
            );
        } else {
            const catDist = dist as CategoricalDistribution;
            return (
                <div className="text-xs text-muted-foreground">
                    {catDist.unique_count} unique
                </div>
            );
        }
    };

    return (
        <Card
            ref={cardRef}
            className="min-w-[200px] w-[200px] flex-shrink-0 hover:shadow-md transition-shadow"
        >
            <CardHeader className="py-2 px-3">
                <div className="flex items-start justify-between gap-1">
                    <CardTitle
                        className="text-xs font-medium truncate flex-1"
                        title={feature}
                    >
                        {feature}
                    </CardTitle>
                    <Badge variant="outline" className="text-[10px] px-1 py-0 flex items-center gap-0.5">
                        {getDataTypeIcon(dataType)}
                        {dataType}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="py-1 px-3">
                {renderMiniChart()}
                <div className="mt-1">
                    {getStatsSummary()}
                </div>
            </CardContent>
        </Card>
    );
}

export function FeatureDistributionCarousel({
    datasetId,
    versionId,
    features,
}: FeatureDistributionCarouselProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [loadedFeatures, setLoadedFeatures] = useState<Set<string>>(new Set());

    const handleFeatureVisible = useCallback((feature: string) => {
        setLoadedFeatures((prev) => new Set(prev).add(feature));
    }, []);

    if (features.length === 0) {
        return (
            <Card>
                <CardContent className="py-8 text-center">
                    <BarChart3 className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">No features available</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-medium">Feature Distributions</h3>
                    <p className="text-xs text-muted-foreground">
                        Scroll horizontally to view all {features.length} features
                        ({loadedFeatures.size} loaded)
                    </p>
                </div>
            </div>

            <div
                ref={containerRef}
                className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent"
                style={{ scrollBehavior: "smooth" }}
            >
                {features.map((feature) => (
                    <FeatureCard
                        key={feature}
                        feature={feature}
                        datasetId={datasetId}
                        versionId={versionId}
                        onVisible={handleFeatureVisible}
                    />
                ))}
            </div>
        </div>
    );
}
