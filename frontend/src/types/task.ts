/**
 * 任务状态枚举
 */
export enum TaskStatus {
    PENDING = 'pending',
    IN_PROGRESS = 'in_progress',
    COMPLETED = 'completed',
    FAILED = 'failed',
    BLOCKED = 'blocked',
    SUCCESS = 'success',
}

/**
 * 验收标准接口
 */
export interface AcceptanceCriteria {
    id?: string;
    description: string;
    status?: 'pending' | 'met' | 'failed';
}

/**
 * PM 任务接口（严格类型版本）
 */
export interface PmTask {
    id: string;
    title: string;
    goal?: string;
    summary?: string;
    status: TaskStatus | string;
    state?: string;
    done: boolean;
    completed?: boolean;
    priority: number;
    acceptance: AcceptanceCriteria[];
}

/**
 * 成功率统计接口
 */
export interface SuccessStats {
    successes: number | null;
    total: number | null;
    rate: number | null;
}

/**
 * PM 状态接口
 */
export interface PmState {
    completed_task_ids?: string[];
    completed_task_count?: number;
    last_director_task_id?: string;
    last_director_task_title?: string;
    last_director_status?: string;
    last_updated_ts?: string;
    pm_iteration?: number | string;
    [key: string]: unknown;
}

/**
 * 任务队列项接口
 */
export interface TaskQueueItem {
    key: string;
    title: string;
    id?: string;
    isCompleted: boolean;
    isCurrent: boolean;
}

/**
 * 进度模式类型
 */
export type ProgressMode = 'done' | 'position' | 'success' | 'idle';
