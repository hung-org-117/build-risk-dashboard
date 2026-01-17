import React from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ConfigFieldSpec } from "@/types";
import { getConfigComponent } from "./fields";

export interface DynamicConfigFieldProps {
    field: ConfigFieldSpec;
    value: unknown;
    onChange: (value: unknown) => void;
    disabled?: boolean;
}

export function DynamicConfigField({ field, value, onChange, disabled }: DynamicConfigFieldProps) {
    // Check for custom component override
    const CustomComponent = getConfigComponent(field.name);
    if (CustomComponent) {
        return (
            <CustomComponent
                field={field}
                value={value}
                onChange={onChange}
                disabled={disabled}
            />
        );
    }

    const currentValue = value ?? field.default ?? "";

    // Parse comma-separated string to array
    const parseArrayValue = (val: string): string[] => {
        return val
            .split(",")
            .map((v) => v.trim().toLowerCase())
            .filter((v) => v.length > 0);
    };

    // Number input
    if (field.type === "int" || field.type === "integer" || field.type === "number") {
        return (
            <Input
                type="number"
                min={1}
                // If it's something like 365 days, fine, but don't strictly enforce max unless in spec
                value={currentValue as number}
                onChange={(e) =>
                    onChange(parseInt(e.target.value) || field.default || 0)
                }
                disabled={disabled}
                className="w-24"
            />
        );
    }

    // Boolean/Select with options
    if (field.options && field.options.length > 0 && field.type !== "list") {
        return (
            <Select
                value={String(currentValue || "")}
                onValueChange={(val) => onChange(val)}
                disabled={disabled}
            >
                <SelectTrigger className="w-40">
                    <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent>
                    {field.options.map((option: string) => (
                        <SelectItem key={option} value={option}>
                            {option}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        );
    }

    // List input (comma-separated)
    if (field.type === "list") {
        const arrayValue = (currentValue as string[]) || [];
        return (
            <Input
                type="text"
                placeholder="Enter values separated by commas"
                value={arrayValue.join(", ")}
                onChange={(e) => onChange(parseArrayValue(e.target.value))}
                disabled={disabled}
                className="flex-1"
            />
        );
    }

    if (field.type === "boolean" || field.type === "bool") {
        return (
            <div className="flex items-center space-x-2">
                <Switch
                    checked={Boolean(currentValue)}
                    onCheckedChange={(checked) => onChange(checked)}
                    disabled={disabled}
                />
                <span className="text-sm text-muted-foreground">
                    {currentValue ? "Enabled" : "Disabled"}
                </span>
            </div>
        );
    }

    // Default: text input
    return (
        <Input
            type="text"
            value={String(currentValue)}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            className="flex-1"
        />
    );
}
