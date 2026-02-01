
import { X, Minus, Maximize2 } from 'lucide-react';
import { useState } from 'react';

export function WindowControls() {
    const [isHovered, setIsHovered] = useState(false);

    const handleMinimize = () => {
        window.harborpilot?.windowControl?.minimize();
    };

    const handleMaximize = () => {
        window.harborpilot?.windowControl?.maximize();
    };

    const handleClose = () => {
        window.harborpilot?.windowControl?.close();
    };

    // If not running in Electron (or preload not loaded), we could hide this.
    // But for design preview, we'll render it.

    return (
        <div
            className="flex items-center gap-2 px-2 no-drag group"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            <button
                onClick={handleClose}
                className="size-3 rounded-full bg-[#ff5f56] border border-[#e0443e] flex items-center justify-center text-[#4a0002]/70 hover:text-[#4a0002] transition-colors shadow-inner"
                aria-label="Close"
            >
                {isHovered && <X className="size-2" strokeWidth={3} />}
            </button>

            <button
                onClick={handleMinimize}
                className="size-3 rounded-full bg-[#ffbd2e] border border-[#dea123] flex items-center justify-center text-[#5c3c00]/70 hover:text-[#5c3c00] transition-colors shadow-inner"
                aria-label="Minimize"
            >
                {isHovered && <Minus className="size-2" strokeWidth={3} />}
            </button>

            <button
                onClick={handleMaximize}
                className="size-3 rounded-full bg-[#27c93f] border border-[#1aab29] flex items-center justify-center text-[#0a4d13]/70 hover:text-[#0a4d13] transition-colors shadow-inner"
                aria-label="Maximize"
            >
                {isHovered && <Maximize2 className="size-2" strokeWidth={3} />}
            </button>
        </div>
    );
}
