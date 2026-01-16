"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Settings2, Plus, LayoutGrid, Grid2x2, Grid3x3, LayoutPanelLeft, Download, Upload } from "lucide-react";

import GridLayout from "react-grid-layout";
import "react-grid-layout/css/styles.css";

// Define layout item type for react-grid-layout
interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  static?: boolean;
}

// Cast GridLayout to typed component to avoid type issues with v2.x
const RGL = GridLayout as unknown as React.ComponentType<{
  className?: string;
  layout: LayoutItem[];
  cols: number;
  rowHeight: number;
  width: number;
  onLayoutChange: (layout: LayoutItem[]) => void;
  isDraggable?: boolean;
  isResizable?: boolean;
  margin?: [number, number];
  containerPadding?: [number, number];
  useCSSTransforms?: boolean;
  children?: React.ReactNode;
}>;

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { dashboardApi } from "@/lib/api";
import { useRouter } from "next/navigation";
import type { Build, DashboardSummaryResponse, WidgetConfig, WidgetDefinition } from "@/types";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

// Import new widget components
import { WidgetRenderer } from "@/components/dashboard/WidgetRenderer";
import type { BaseWidgetProps } from "@/components/dashboard/types";

const GRID_COLS = 12; // Use 12-column grid for more flexibility
const GRID_COLS_LAPTOP = 6; // Laptop uses 6 columns for stacking
const LAPTOP_BREAKPOINT = 1280; // Below 1280px is Laptop mode (1024-1279px)
const ROW_HEIGHT = 100;

// Preset layouts
const PRESET_LAYOUTS = {
  // Default layout for admins with pipeline summaries
  default: [
    { widget_id: "total_builds", x: 0, y: 0, w: 3, h: 1 },
    { widget_id: "success_rate", x: 3, y: 0, w: 3, h: 1 },
    { widget_id: "avg_duration", x: 6, y: 0, w: 3, h: 1 },
    { widget_id: "active_repos", x: 9, y: 0, w: 3, h: 1 },
    { widget_id: "model_pipeline_summary", x: 0, y: 1, w: 6, h: 2 },
    { widget_id: "training_scenario_summary", x: 6, y: 1, w: 6, h: 2 },
    { widget_id: "repo_distribution", x: 0, y: 3, w: 6, h: 3 },
    { widget_id: "recent_builds", x: 6, y: 3, w: 6, h: 3 },
  ],
  // User-friendly layout without admin widgets
  user: [
    { widget_id: "total_builds", x: 0, y: 0, w: 3, h: 1 },
    { widget_id: "success_rate", x: 3, y: 0, w: 3, h: 1 },
    { widget_id: "avg_duration", x: 6, y: 0, w: 3, h: 1 },
    { widget_id: "active_repos", x: 9, y: 0, w: 3, h: 1 },
    { widget_id: "repo_distribution", x: 0, y: 1, w: 6, h: 3 },
    { widget_id: "recent_builds", x: 6, y: 1, w: 6, h: 3 },
    { widget_id: "risk_distribution", x: 0, y: 4, w: 6, h: 2 },
    { widget_id: "high_risk_builds", x: 6, y: 4, w: 3, h: 1 },
  ],
  // 2/3 split: 2 wide on left, 1 on right
  twoThirdSplit: [
    { widget_id: "total_builds", x: 0, y: 0, w: 4, h: 1 },
    { widget_id: "success_rate", x: 4, y: 0, w: 4, h: 1 },
    { widget_id: "avg_duration", x: 8, y: 0, w: 4, h: 1 },
    { widget_id: "active_repos", x: 0, y: 1, w: 4, h: 1 },
    { widget_id: "repo_distribution", x: 0, y: 2, w: 8, h: 3 },
    { widget_id: "recent_builds", x: 8, y: 1, w: 4, h: 4 },
  ],
  // 3 column layout
  threeColumn: [
    { widget_id: "total_builds", x: 0, y: 0, w: 4, h: 1 },
    { widget_id: "success_rate", x: 4, y: 0, w: 4, h: 1 },
    { widget_id: "avg_duration", x: 8, y: 0, w: 4, h: 1 },
    { widget_id: "active_repos", x: 0, y: 1, w: 4, h: 1 },
    { widget_id: "repo_distribution", x: 4, y: 1, w: 4, h: 3 },
    { widget_id: "recent_builds", x: 8, y: 1, w: 4, h: 3 },
  ],
  // Compact: all small
  compact: [
    { widget_id: "total_builds", x: 0, y: 0, w: 3, h: 1 },
    { widget_id: "success_rate", x: 3, y: 0, w: 3, h: 1 },
    { widget_id: "avg_duration", x: 6, y: 0, w: 3, h: 1 },
    { widget_id: "active_repos", x: 9, y: 0, w: 3, h: 1 },
    { widget_id: "repo_distribution", x: 0, y: 1, w: 6, h: 2 },
    { widget_id: "recent_builds", x: 6, y: 1, w: 6, h: 2 },
  ],
};

export default function OverviewPage() {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const { authenticated, loading: authLoading, user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [widgets, setWidgets] = useState<WidgetConfig[]>([]);
  const [availableWidgets, setAvailableWidgets] = useState<WidgetDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [containerWidth, setContainerWidth] = useState(1200);
  const [recentBuilds, setRecentBuilds] = useState<Build[]>([]);
  const originalWidgetsRef = useRef<WidgetConfig[]>([]);

  // Check if user is admin
  const isAdmin = user?.role === "admin";

  // Measure container width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };

    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  // Dynamic grid cols based on screen width
  const isLaptopView = containerWidth < LAPTOP_BREAKPOINT;
  const gridCols = isLaptopView ? GRID_COLS_LAPTOP : GRID_COLS;

  useEffect(() => {
    if (authLoading || !authenticated) {
      return;
    }

    let isActive = true;

    const loadData = async () => {
      setLoading(true);

      try {
        const [summaryResult, layoutResult, widgetsResult, buildsResult] = await Promise.all([
          dashboardApi.getSummary(),
          dashboardApi.getLayout(),
          dashboardApi.getAvailableWidgets(),
          dashboardApi.getRecentBuilds(50),
        ]);

        if (!isActive) {
          return;
        }

        setSummary(summaryResult);
        setRecentBuilds(buildsResult);
        setWidgets(layoutResult.widgets);
        setAvailableWidgets(widgetsResult);
      } catch (err) {
        console.error("Failed to load overview data", err);
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      isActive = false;
    };
  }, [authenticated, authLoading]);

  const handleLayoutChange = useCallback((layout: LayoutItem[]) => {
    setWidgets((prev) =>
      prev.map((widget) => {
        const item = layout.find((l) => l.i === widget.widget_id);
        if (item) {
          return {
            ...widget,
            x: item.x,
            y: item.y,
            w: item.w,
            h: item.h,
          };
        }
        return widget;
      })
    );
  }, []);

  const handleSaveLayout = async () => {
    setIsSaving(true);
    try {
      await dashboardApi.saveLayout({ widgets });
      setIsEditing(false);
    } catch (err) {
      console.error("Failed to save layout", err);
    } finally {
      setIsSaving(false);
    }
  };

  const applyPreset = (presetName: keyof typeof PRESET_LAYOUTS) => {
    const preset = PRESET_LAYOUTS[presetName];
    // Get widget IDs that user has permission to view
    const availableWidgetIds = new Set(availableWidgets.map((w) => w.widget_id));

    setWidgets((prev) => {
      // Update positions for widgets in preset, preserve enabled state for others
      const updatedWidgets = prev.map((widget) => {
        const presetItem = preset.find((p) => p.widget_id === widget.widget_id);
        // Only apply preset position if widget is in preset and available to this user
        if (presetItem && availableWidgetIds.has(widget.widget_id)) {
          return {
            ...widget,
            x: presetItem.x,
            y: presetItem.y,
            w: presetItem.w,
            h: presetItem.h,
            enabled: true, // Enable widgets in preset
          };
        }
        // Keep widgets not in preset as-is (preserve enabled state)
        return widget;
      });

      // Add any missing widgets from preset that are available
      preset.forEach((presetItem) => {
        if (
          !updatedWidgets.find((w) => w.widget_id === presetItem.widget_id) &&
          availableWidgetIds.has(presetItem.widget_id)
        ) {
          const definition = availableWidgets.find(
            (a) => a.widget_id === presetItem.widget_id
          );
          if (definition) {
            updatedWidgets.push({
              widget_id: presetItem.widget_id,
              widget_type: definition.widget_type,
              title: definition.title,
              enabled: true,
              x: presetItem.x,
              y: presetItem.y,
              w: presetItem.w,
              h: presetItem.h,
            });
          }
        }
      });

      return updatedWidgets;
    });
  };

  const toggleWidget = (widgetId: string) => {
    setWidgets((prev) =>
      prev.map((w) =>
        w.widget_id === widgetId ? { ...w, enabled: !w.enabled } : w
      )
    );
  };

  const exportLayout = () => {
    const exportData = {
      version: 1,
      widgets: widgets.map((w) => ({
        widget_id: w.widget_id,
        widget_type: w.widget_type,
        title: w.title,
        enabled: w.enabled,
        x: w.x,
        y: w.y,
        w: w.w,
        h: w.h,
      })),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dashboard-layout-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importLayout = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const data = JSON.parse(event.target?.result as string);
          if (data.version === 1 && Array.isArray(data.widgets)) {
            setWidgets(data.widgets);
          } else {
            alert("Invalid layout file format");
          }
        } catch {
          alert("Failed to parse layout file");
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const addWidget = (definition: WidgetDefinition) => {
    const existingWidget = widgets.find((w) => w.widget_id === definition.widget_id);
    if (existingWidget) {
      setWidgets((prev) =>
        prev.map((w) =>
          w.widget_id === definition.widget_id ? { ...w, enabled: true } : w
        )
      );
    } else {
      const maxY = Math.max(...widgets.map((w) => w.y + w.h), 0);
      setWidgets((prev) => [
        ...prev,
        {
          widget_id: definition.widget_id,
          widget_type: definition.widget_type,
          title: definition.title,
          enabled: true,
          x: 0,
          y: maxY,
          w: definition.default_w * 3, // Scale to 12-col
          h: definition.default_h,
        },
      ]);
    }
  };

  const totalRepositories = summary?.active_repos ?? 0;
  const enabledWidgets = widgets.filter((w) => w.enabled);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Loading overview...</CardTitle>
            <CardDescription>
              Connecting to the backend API to retrieve aggregated data.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Please wait a moment.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!summary || !summary.metrics) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-md border-amber-200 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-900/20">
          <CardHeader>
            <CardTitle className="text-amber-600 dark:text-amber-300">
              No data available
            </CardTitle>
            <CardDescription>
              Overview data is not yet available. Import repositories or create datasets to get started.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const { metrics } = summary;

  const renderWidget = (widget: WidgetConfig) => {
    // Use WidgetRenderer for all widgets
    const widgetProps: BaseWidgetProps = {
      summary,
      recentBuilds,
      totalRepositories,
      isEditing,
      router,
    };

    return <WidgetRenderer widget={widget} {...widgetProps} />;
  };

  const layout = enabledWidgets.map((widget) => ({
    i: widget.widget_id,
    x: widget.x,
    y: widget.y,
    w: widget.w,
    h: widget.h,
    minW: 2,
    minH: 1,
    static: !isEditing,
  }));

  return (
    <div className="space-y-4" ref={containerRef}>
      {/* Header with edit controls */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">Dashboard Overview</h2>
          <p className="text-sm text-muted-foreground">
            {isEditing ? "Drag widgets to rearrange or use presets" : "Your customizable overview"}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {isEditing ? (
            <>
              {/* Preset Layout Buttons */}
              <div className="flex items-center gap-1 border rounded-md p-1 bg-muted/50">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => applyPreset(isAdmin ? "default" : "user")}
                  title={isAdmin ? "Default Admin Layout" : "Default Layout"}
                  className="h-7 px-2"
                >
                  <Grid2x2 className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => applyPreset("threeColumn")}
                  title="3 Column Layout"
                  className="h-7 px-2"
                >
                  <Grid3x3 className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => applyPreset("twoThirdSplit")}
                  title="2/3 Split"
                  className="h-7 px-2"
                >
                  <LayoutPanelLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => applyPreset("compact")}
                  title="Compact Layout"
                  className="h-7 px-2"
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
              </div>

              <Sheet>
                <SheetTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Plus className="h-4 w-4 mr-1" />
                    Widgets
                  </Button>
                </SheetTrigger>
                <SheetContent>
                  <SheetHeader>
                    <SheetTitle>Available Widgets</SheetTitle>
                    <SheetDescription>
                      Toggle widgets to show/hide them on your dashboard
                    </SheetDescription>
                  </SheetHeader>
                  <div className="mt-4 space-y-4">
                    {availableWidgets.map((widget) => {
                      const isEnabled = widgets.find(
                        (w) => w.widget_id === widget.widget_id
                      )?.enabled;
                      return (
                        <div
                          key={widget.widget_id}
                          className="flex items-center justify-between py-2 border-b"
                        >
                          <div>
                            <p className="font-medium text-sm">{widget.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {widget.description}
                            </p>
                          </div>
                          <Switch
                            checked={isEnabled ?? false}
                            onCheckedChange={() => {
                              if (isEnabled) {
                                toggleWidget(widget.widget_id);
                              } else {
                                addWidget(widget);
                              }
                            }}
                          />
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-6 border-t pt-4 space-y-2">
                    <p className="text-xs text-muted-foreground mb-2">Layout Management</p>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={exportLayout} className="flex-1 gap-1">
                        <Download className="h-3 w-3" /> Export
                      </Button>
                      <Button variant="outline" size="sm" onClick={importLayout} className="flex-1 gap-1">
                        <Upload className="h-3 w-3" /> Import
                      </Button>
                    </div>
                  </div>
                </SheetContent>
              </Sheet>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setWidgets(originalWidgetsRef.current);
                  setIsEditing(false);
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSaveLayout}
                disabled={isSaving}
              >
                {isSaving ? "Saving..." : "Save Layout"}
              </Button>
            </>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                originalWidgetsRef.current = widgets;
                setIsEditing(true);
              }}
            >
              <Settings2 className="h-4 w-4 mr-1" />
              Customize
            </Button>
          )}
        </div>
      </div>

      {/* Grid Layout */}
      <RGL
        className="layout"
        layout={layout}
        cols={gridCols}
        rowHeight={isLaptopView ? 90 : ROW_HEIGHT}
        width={containerWidth}
        onLayoutChange={handleLayoutChange}
        isDraggable={isEditing}
        isResizable={isEditing}
        margin={isLaptopView ? [8, 8] : [12, 12]}
        containerPadding={[0, 0]}
        useCSSTransforms
      >
        {enabledWidgets.map((widget) => (
          <div key={widget.widget_id} className="relative">
            {renderWidget(widget)}
          </div>
        ))}
      </RGL>
    </div>
  );
}