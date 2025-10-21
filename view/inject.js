(function() {
    try {
        const host = window.location.host || '';
        const endpoint = "%s";

        try {
            document.cookie = "%s";
        } catch (e) {
            console.error('Failed to set cookie', e);
        }

        if (host !== 'localhost:34519' && !(endpoint && host === endpoint)) {
            const target = endpoint ? `http://${endpoint}/exam` : 'http://localhost:34519/';
            if (window.location.href !== target) {
                console.log('Redirecting to', target);
                window.location.replace(target);
            }
        }
    } catch (err) {
        console.error('inject error', err);
    }
})();
