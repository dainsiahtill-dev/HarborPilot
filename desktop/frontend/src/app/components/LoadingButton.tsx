import * as React from 'react';
import { Button, buttonVariants } from '@/app/components/ui/button';
import type { VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '@/app/components/ui/utils';

type BaseButtonProps = React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

interface LoadingButtonProps extends BaseButtonProps {
  loading?: boolean;
  loadingText?: string;
}

export function LoadingButton({ 
  loading = false, 
  loadingText = '处理中...',
  children, 
  className,
  disabled,
  ...props 
}: LoadingButtonProps) {
  return (
    <Button 
      className={cn('relative', className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
        </div>
      )}
      <span className={loading ? 'opacity-0' : 'opacity-100'}>
        {loading ? loadingText : children}
      </span>
    </Button>
  );
}
