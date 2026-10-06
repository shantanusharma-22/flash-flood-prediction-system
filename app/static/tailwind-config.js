// Tailwind runtime configuration (loaded right after the Tailwind CDN script).
// Kept in an external file so the dashboard can ship a strict script-src CSP
// with no 'unsafe-inline'.
tailwind.config = {
    darkMode: 'class',
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
                heading: ['Outfit', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            colors: {
                hazard: {
                    red: '#ef4444',
                    orange: '#f97316',
                    yellow: '#eab308',
                    green: '#10b981'
                }
            }
        }
    }
};
