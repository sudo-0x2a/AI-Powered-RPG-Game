// Thin wrapper to keep existing HTML entry point stable
// Works even if this script is included as a classic script (non-module)
(function loadModule() {
    try {
        const script = document.createElement('script');
        script.type = 'module';
        // Use absolute path so the dev server can resolve it
        script.src = '/src/frontend/main.js';
        const current = document.currentScript;
        if (current && current.parentNode) {
            current.parentNode.insertBefore(script, current.nextSibling);
        } else {
            document.head.appendChild(script);
        }
    } catch (e) {
        console.error('Failed to bootstrap module main.js', e);
    }
})();


