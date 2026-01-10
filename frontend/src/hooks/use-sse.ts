"use client";

import { useCallback, useEffect, useRef, useState } from "react";

function buildSSEUrl(path: string): string {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return `${baseUrl}${normalizedPath}`;
}

export interface UseSSEOptions {
    path: string;
    autoConnect?: boolean;
    reconnectDelay?: number;
    onMessage?: (data: any) => void;
    onOpen?: () => void;
    onError?: (error: Event) => void;
}

export interface UseSSEReturn {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
}

/**
 * Hook for connecting to a specific SSE endpoint.
 * 
 * @example
 * const { isConnected } = useSSE({
 *   path: `/sse/enrichment/${jobId}`,
 *   onMessage: (data) => console.log('Progress:', data),
 * });
 */
export function useSSE({
    path,
    autoConnect = true,
    reconnectDelay = 5000,
    onMessage,
    onOpen,
    onError,
}: UseSSEOptions): UseSSEReturn {
    const [isConnected, setIsConnected] = useState(false);
    const eventSourceRef = useRef<EventSource | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const isMountedRef = useRef(true);

    const onMessageRef = useRef(onMessage);
    const onOpenRef = useRef(onOpen);
    const onErrorRef = useRef(onError);

    useEffect(() => {
        onMessageRef.current = onMessage;
        onOpenRef.current = onOpen;
        onErrorRef.current = onError;
    }, [onMessage, onOpen, onError]);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setIsConnected(false);
    }, []);

    const connect = useCallback(() => {
        // Don't connect if already connected
        if (eventSourceRef.current?.readyState === EventSource.OPEN ||
            eventSourceRef.current?.readyState === EventSource.CONNECTING) {
            return;
        }

        try {
            const sseUrl = buildSSEUrl(path);
            const eventSource = new EventSource(sseUrl, { withCredentials: true });
            eventSourceRef.current = eventSource;

            eventSource.onopen = () => {
                if (!isMountedRef.current) return;
                setIsConnected(true);
                if (reconnectTimeoutRef.current) {
                    clearTimeout(reconnectTimeoutRef.current);
                    reconnectTimeoutRef.current = null;
                }
                onOpenRef.current?.();
            };

            eventSource.onmessage = (event) => {
                if (!isMountedRef.current) return;
                try {
                    const data = JSON.parse(event.data);

                    // Skip heartbeats
                    if (data.type === "heartbeat") return;

                    onMessageRef.current?.(data);
                } catch {
                    // If not JSON, pass raw data
                    onMessageRef.current?.(event.data);
                }
            };

            eventSource.onerror = (error) => {
                if (!isMountedRef.current) return;
                setIsConnected(false);
                onErrorRef.current?.(error);
                eventSource.close();
                eventSourceRef.current = null;

                // Auto-reconnect if enabled
                if (reconnectDelay > 0 && !reconnectTimeoutRef.current) {
                    reconnectTimeoutRef.current = setTimeout(() => {
                        if (isMountedRef.current) {
                            reconnectTimeoutRef.current = null;
                            connect();
                        }
                    }, reconnectDelay);
                }
            };
        } catch (err) {
            console.error("SSE connection error:", err);
        }
    }, [path, reconnectDelay]);

    // Auto-connect on mount
    useEffect(() => {
        isMountedRef.current = true;
        if (autoConnect) {
            connect();
        }
        return () => {
            isMountedRef.current = false;
            disconnect();
        };
    }, [autoConnect, connect, disconnect]);

    return {
        isConnected,
        connect,
        disconnect,
    };
}
