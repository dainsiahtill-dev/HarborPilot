/**
 * 性能监控工具
 */

import { useEffect, useRef } from 'react';

/**
 * 性能监控 Hook - 测量组件渲染时间
 */
export function useRenderTime(componentName: string, threshold = 100) {
    const renderStartTime = useRef(performance.now());

    useEffect(() => {
        const renderEndTime = performance.now();
        const renderDuration = renderEndTime - renderStartTime.current;

        if (renderDuration > threshold) {
            console.warn(
                `⚠️ [Performance] ${componentName} 渲染耗时: ${renderDuration.toFixed(2)}ms (阈值: ${threshold}ms)`
            );
        } else if (process.env.NODE_ENV === 'development') {
            console.log(
                `✅ [Performance] ${componentName} 渲染耗时: ${renderDuration.toFixed(2)}ms`
            );
        }

        // 重置计时器
        renderStartTime.current = performance.now();
    });
}

/**
 * 性能监控 HOC - 包装组件并监控渲染性能
 */
export function withPerformanceMonitoring<P extends object>(
    Component: React.ComponentType<P>,
    componentName?: string
) {
    const displayName = componentName || Component.displayName || Component.name || 'Component';

    const MonitoredComponent = (props: P) => {
        useRenderTime(displayName);
        return <Component {...props} />;
    };

    MonitoredComponent.displayName = `withPerformanceMonitoring(${displayName})`;

    return MonitoredComponent;
}

/**
 * 记录组件挂载和卸载
 */
export function useComponentLifecycle(componentName: string) {
    useEffect(() => {
        console.log(`🔵 [Lifecycle] ${componentName} 已挂载`);

        return () => {
            console.log(`🔴 [Lifecycle] ${componentName} 已卸载`);
        };
    }, [componentName]);
}
