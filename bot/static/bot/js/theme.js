document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme);

    document.querySelectorAll('[data-bs-theme]').forEach(btn => {
        btn.addEventListener('click', () => {
            const theme = btn.dataset.bsTheme;
            document.documentElement.setAttribute('data-bs-theme', theme);
            localStorage.setItem('theme', theme);
        });
    });
});