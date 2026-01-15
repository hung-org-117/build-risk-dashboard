import { useCallback, useRef, useEffect } from "react";

/**
 * Returns a debounced version of the callback that delays invoking
 * until after `delay` milliseconds have elapsed since the last invocation.
 * 
 * @param callback - The function to debounce
 * @param delay - Delay in milliseconds (default: 500ms)
 * @param options - Additional options
 *   - leading: Execute on the leading edge (default: true)
 *   - trailing: Execute on the trailing edge (default: true)
 * 
 * @example
 * const debouncedFetch = useDebouncedCallback(fetchData, 500);
 * // Call debouncedFetch() multiple times - only executes once per 500ms window
 */
export function useDebouncedCallback<T extends (...args: any[]) => any>(
    callback: T,
    delay: number = 500,
    options: { leading?: boolean; trailing?: boolean } = {}
): (...args: Parameters<T>) => void {
    const { leading = true, trailing = true } = options;

    const timeoutRef = useRef<NodeJS.Timeout | null>(null);
    const callbackRef = useRef(callback);
    const lastArgsRef = useRef<Parameters<T> | null>(null);
    const lastCallTimeRef = useRef<number>(0);
    const isLeadingInvokedRef = useRef(false);

    // Keep callback ref up to date
    useEffect(() => {
        callbackRef.current = callback;
    }, [callback]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    return useCallback(
        (...args: Parameters<T>) => {
            const now = Date.now();
            lastArgsRef.current = args;

            const invokeCallback = () => {
                if (lastArgsRef.current) {
                    callbackRef.current(...lastArgsRef.current);
                }
            };

            // Clear existing timeout
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }

            // Check if we should invoke on leading edge
            const shouldInvokeLeading =
                leading && !isLeadingInvokedRef.current;

            if (shouldInvokeLeading) {
                isLeadingInvokedRef.current = true;
                invokeCallback();
            }

            // Set up trailing edge invocation
            if (trailing) {
                timeoutRef.current = setTimeout(() => {
                    // Only invoke on trailing if we didn't just invoke on leading
                    // or if there were calls after the leading invocation
                    if (!shouldInvokeLeading || lastCallTimeRef.current > now) {
                        invokeCallback();
                    }
                    isLeadingInvokedRef.current = false;
                    timeoutRef.current = null;
                }, delay);
            } else {
                // Reset leading flag after delay even without trailing
                timeoutRef.current = setTimeout(() => {
                    isLeadingInvokedRef.current = false;
                    timeoutRef.current = null;
                }, delay);
            }

            lastCallTimeRef.current = now;
        },
        [delay, leading, trailing]
    );
}

/**
 * Simplified debounce that only fires on trailing edge.
 * Useful for SSE updates where we want to batch rapid updates.
 */
export function useTrailingDebounce<T extends (...args: any[]) => any>(
    callback: T,
    delay: number = 300
): (...args: Parameters<T>) => void {
    return useDebouncedCallback(callback, delay, {
        leading: false,
        trailing: true,
    });
}
