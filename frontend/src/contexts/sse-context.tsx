"use client";

import React, {
    createContext,
    useContext,
    useEffect,
    useRef,
    useState,
    useCallback,
} from "react";
import { useToast } from "@/components/ui/use-toast";

type SSEMessage = {
    type: string;
    payload?: any;
    // Allow other fields for direct event payloads
    [key: string]: any;
};

type SSEContextType = {
    isConnected: boolean;
    subscribe: (eventType: string, callback: (payload: any) => void) => () => void;
};

const SSEContext = createContext<SSEContextType | undefined>(undefined);

export function SSEProvider({ children }: { children: React.ReactNode }) {
    const [isConnected, setIsConnected] = useState(false);
    const eventSourceRef = useRef<EventSource | null>(null);
    const subscribersRef = useRef<
        Record<string, Set<(payload: any) => void>>
    >({});
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const { toast } = useToast();

    const connect = useCallback(() => {
        if (eventSourceRef.current?.readyState === EventSource.OPEN) return;

        // Close existing connection if any
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        // Get token from cookie for SSE auth (EventSource can't send headers)
        const getToken = () => {
            const match = document.cookie.match(/(?:^|; )access_token=([^;]*)/);
            return match ? decodeURIComponent(match[1]) : null;
        };
        const token = getToken();

        const baseUrl = process.env.NEXT_PUBLIC_API_URL
            ? `${process.env.NEXT_PUBLIC_API_URL}/sse/events`
            : "http://localhost:8000/api/sse/events";

        // Append token as query param for SSE auth
        const sseUrl = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;

        const eventSource = new EventSource(sseUrl, { withCredentials: true });

        eventSource.onopen = () => {
            console.log("SSE connected");
            setIsConnected(true);
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }
        };

        eventSource.onerror = (error) => {
            console.error("SSE error:", error);
            setIsConnected(false);
            eventSource.close();
            eventSourceRef.current = null;

            // Attempt reconnect after 3 seconds
            if (!reconnectTimeoutRef.current) {
                reconnectTimeoutRef.current = setTimeout(() => {
                    console.log("Attempting SSE reconnect...");
                    reconnectTimeoutRef.current = null;
                    connect();
                }, 3000);
            }
        };

        // Handler for all messages
        const handleMessage = (event: MessageEvent) => {
            try {
                const message: SSEMessage = JSON.parse(event.data);
                const eventType = message.type;

                // Skip heartbeats
                if (eventType === "heartbeat") return;

                // Get payload - some events have it nested, some have it at top level
                const payload = message.payload || message;

                // Handle User Notification (Toast)
                if (eventType === "SYSTEM.NOTIFICATION") {
                    toast({
                        title: payload.title,
                        description: payload.message,
                        variant: "default",
                    });
                }

                // Notify subscribers via context
                if (subscribersRef.current[eventType]) {
                    console.log(`[SSE] Dispatching ${eventType} to ${subscribersRef.current[eventType].size} subscribers:`, payload);
                    subscribersRef.current[eventType].forEach((callback) => {
                        try {
                            callback(payload);
                        } catch (err) {
                            console.error(`Error in SSE subscriber for ${eventType}:`, err);
                        }
                    });
                }

                // Also dispatch as window custom event for components that need it
                // Naming convention: {PIPELINE}.{ENTITY}.{ACTION}
                // - MODEL.*: Model Training Pipeline events  
                // - SCENARIO.*: Training Scenario Pipeline events
                // - SYSTEM.*: System-wide events
                const broadcastEventTypes = [
                    "MODEL.REPO.UPDATED",
                    "MODEL.INGESTION.PROGRESS",
                    "MODEL.PROCESSING.UPDATED",
                    "MODEL.PREDICTION.UPDATED",
                    "SCENARIO.UPDATED",
                    "SCENARIO.INGESTION.UPDATED",
                    "SCENARIO.PROCESSING.UPDATED",
                    "SCENARIO.SCAN.UPDATED",
                    "SOURCE.VALIDATION.UPDATED",
                    "SYSTEM.NOTIFICATION",
                ];

                if (broadcastEventTypes.includes(eventType)) {
                    window.dispatchEvent(
                        new CustomEvent(eventType, { detail: payload })
                    );
                }
            } catch (e) {
                console.error("Failed to parse SSE message:", e);
            }
        };

        // Listen for default message event
        eventSource.onmessage = handleMessage;

        // Explicitly listen for named events because EventSource doesn't fire onmessage for named events
        // Naming convention: {PIPELINE}.{ENTITY}.{ACTION}
        const eventTypes = [
            "MODEL.REPO.UPDATED",
            "MODEL.INGESTION.PROGRESS",
            "MODEL.PROCESSING.UPDATED",
            "MODEL.PREDICTION.UPDATED",
            "SCENARIO.UPDATED",
            "SCENARIO.INGESTION.UPDATED",
            "SCENARIO.PROCESSING.UPDATED",
            "SCENARIO.SCAN.UPDATED",
            "SOURCE.VALIDATION.UPDATED",
            "SYSTEM.NOTIFICATION",
        ];

        eventTypes.forEach(type => {
            eventSource.addEventListener(type, handleMessage);
        });

        eventSourceRef.current = eventSource;
    }, [toast]);

    useEffect(() => {
        connect();
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, [connect]);

    const subscribe = useCallback(
        (eventType: string, callback: (payload: any) => void) => {
            if (!subscribersRef.current[eventType]) {
                subscribersRef.current[eventType] = new Set();
            }
            subscribersRef.current[eventType].add(callback);

            console.log(`[SSE Context] Subscribed to ${eventType}. Total subscribers: ${subscribersRef.current[eventType].size}`);

            return () => {
                if (subscribersRef.current[eventType]) {
                    subscribersRef.current[eventType].delete(callback);
                    console.log(`[SSE Context] Unsubscribed from ${eventType}. Remaining: ${subscribersRef.current[eventType]?.size || 0}`);
                    if (subscribersRef.current[eventType].size === 0) {
                        delete subscribersRef.current[eventType];
                    }
                }
            };
        },
        []
    );

    return (
        <SSEContext.Provider value={{ isConnected, subscribe }}>
            {children}
        </SSEContext.Provider>
    );
}

export function useSSE() {
    const context = useContext(SSEContext);
    if (context === undefined) {
        throw new Error("useSSE must be used within an SSEProvider");
    }
    return context;
}
