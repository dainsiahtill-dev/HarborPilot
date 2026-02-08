export type ProgressMode = 'done' | 'position' | 'idle' | 'success';

export interface PmTask {
  id?: string;
  title?: string;
  goal?: string;
  priority?: number;
  acceptance?: Array<{ description?: string }>;
  status?: 'pending' | 'in_progress' | 'completed';
}

export interface TaskQueueItem {
  key: string;
  title: string;
  isCurrent: boolean;
  isCompleted: boolean;
}
