import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

interface DefaultProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function DefaultProviderSettings({
  provider,
  onUpdate,
  onValidate
}: DefaultProviderSettingsProps) {
  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Generic Provider Settings</h5>
        <div className="bg-black/30 rounded-lg p-3 border border-white/10">
          <p className="text-xs text-text-dim">
            This provider uses the default configuration. Specific settings may be available depending on the provider type.
          </p>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
