/* ==========================================================================
   AI Code Review Agent — GitHub Pages Blog
   Scroll animations, Chart.js, nav behavior, mobile toggle
   ========================================================================== */

(function () {
  'use strict';

  /* ---------- Theme Toggle ---------- */

  const html = document.documentElement;
  const themeToggle = document.querySelector('.theme-toggle');

  function applyTheme(theme) {
    html.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  const savedTheme = localStorage.getItem('theme');
  if (savedTheme) {
    applyTheme(savedTheme);
  } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
    applyTheme('light');
  }
  // else: no attribute set, dark is the default via :root

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const current = html.getAttribute('data-theme');
      applyTheme(current === 'light' ? 'dark' : 'light');
    });
  }

  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      applyTheme(e.matches ? 'light' : 'dark');
    }
  });

  /* ---------- Scroll to Top ---------- */

  const scrollToTopBtn = document.querySelector('.scroll-to-top');

  if (scrollToTopBtn) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 400) {
        scrollToTopBtn.classList.add('visible');
      } else {
        scrollToTopBtn.classList.remove('visible');
      }
    }, { passive: true });

    scrollToTopBtn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  /* ---------- Scroll Reveal (IntersectionObserver) ---------- */

  const revealElements = document.querySelectorAll('[data-animate]');

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const delay = entry.target.dataset.delay || 0;
            setTimeout(() => {
              entry.target.classList.add('visible');
            }, Number(delay));
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );

    revealElements.forEach((el) => observer.observe(el));
  } else {
    revealElements.forEach((el) => el.classList.add('visible'));
  }

  /* ---------- Navigation: Scroll State ---------- */

  const nav = document.querySelector('.nav');

  function updateNavScroll() {
    if (window.scrollY > 40) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }
  }

  window.addEventListener('scroll', updateNavScroll, { passive: true });
  updateNavScroll();

  /* ---------- Navigation: Active Link Tracking ---------- */

  const sections = document.querySelectorAll('.section[id]');
  const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');

  function updateActiveLink() {
    let current = '';
    const scrollY = window.scrollY + 120;

    sections.forEach((section) => {
      if (scrollY >= section.offsetTop) {
        current = section.getAttribute('id');
      }
    });

    navLinks.forEach((link) => {
      link.classList.remove('active');
      if (link.getAttribute('href') === '#' + current) {
        link.classList.add('active');
      }
    });
  }

  window.addEventListener('scroll', updateActiveLink, { passive: true });
  updateActiveLink();

  /* ---------- Navigation: Smooth Scroll ---------- */

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
        // Close mobile nav if open
        document.querySelector('.nav-links').classList.remove('open');
        document.querySelector('.nav-hamburger').classList.remove('open');
      }
    });
  });

  /* ---------- Mobile Nav Toggle ---------- */

  const hamburger = document.querySelector('.nav-hamburger');
  const navLinksEl = document.querySelector('.nav-links');

  if (hamburger) {
    hamburger.addEventListener('click', () => {
      hamburger.classList.toggle('open');
      navLinksEl.classList.toggle('open');
    });
  }

  /* ---------- Chart.js: Metric Gauges ---------- */

  const gaugeConfig = [
    { id: 'gauge-precision', value: 68.2, color: '#6C5CE7' },
    { id: 'gauge-recall', value: 50.0, color: '#4DA8FF' },
    { id: 'gauge-f1', value: 57.7, color: '#00D68F' },
    { id: 'gauge-fpr', value: 31.8, color: '#FF6B6B' },
  ];

  gaugeConfig.forEach((g) => {
    const canvas = document.getElementById(g.id);
    if (!canvas) return;

    new Chart(canvas, {
      type: 'doughnut',
      data: {
        datasets: [
          {
            data: [g.value, 100 - g.value],
            backgroundColor: [g.color, 'rgba(255,255,255,0.04)'],
            borderWidth: 0,
            borderRadius: 6,
          },
        ],
      },
      options: {
        cutout: '78%',
        responsive: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: {
          animateRotate: true,
          duration: 1200,
          easing: 'easeOutQuart',
        },
      },
    });
  });

  /* ---------- Chart.js: Per-Category Bar Chart ---------- */

  const catCanvas = document.getElementById('chart-categories');
  if (catCanvas) {
    new Chart(catCanvas, {
      type: 'bar',
      data: {
        labels: ['Logic', 'Bug', 'Security'],
        datasets: [
          {
            label: 'Detection Accuracy',
            data: [66.7, 50.0, 47.6],
            backgroundColor: ['#00D68F', '#4DA8FF', '#6C5CE7'],
            borderRadius: 6,
            barThickness: 36,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            max: 100,
            grid: { color: 'rgba(255,255,255,0.04)' },
            ticks: {
              color: '#5A5A72',
              font: { family: "'Inter', sans-serif", size: 12 },
              callback: (v) => v + '%',
            },
          },
          y: {
            grid: { display: false },
            ticks: {
              color: '#E8E8ED',
              font: { family: "'Inter', sans-serif", size: 13, weight: 600 },
            },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1A1A2E',
            titleColor: '#E8E8ED',
            bodyColor: '#8888A0',
            borderColor: 'rgba(255,255,255,0.06)',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            callbacks: {
              label: (ctx) => ctx.parsed.x + '% accuracy',
            },
          },
        },
        animation: { duration: 1000, easing: 'easeOutQuart' },
      },
    });
  }

  /* ---------- Chart.js: Per-Benchmark Radar ---------- */

  const radarCanvas = document.getElementById('chart-radar');
  if (radarCanvas) {
    new Chart(radarCanvas, {
      type: 'radar',
      data: {
        labels: [
          'Buffer Overflow',
          'Hardcoded Secret',
          'Insecure Deser.',
          'Logic Error',
          'Missing Valid.',
          'Null Reference',
          'Off-by-One',
          'Race Condition',
          'SQL Injection',
          'XSS',
        ],
        datasets: [
          {
            label: 'F1 Score',
            data: [80, 66.7, 66.7, 66.7, 57.1, 0, 50, 0, 66.7, 50],
            borderColor: '#6C5CE7',
            backgroundColor: 'rgba(108, 92, 231, 0.12)',
            pointBackgroundColor: '#6C5CE7',
            pointBorderColor: '#6C5CE7',
            pointRadius: 4,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            beginAtZero: true,
            max: 100,
            grid: { color: 'rgba(255,255,255,0.06)' },
            angleLines: { color: 'rgba(255,255,255,0.06)' },
            pointLabels: {
              color: '#8888A0',
              font: { family: "'Inter', sans-serif", size: 11 },
            },
            ticks: {
              display: false,
              stepSize: 25,
            },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1A1A2E',
            titleColor: '#E8E8ED',
            bodyColor: '#8888A0',
            borderColor: 'rgba(255,255,255,0.06)',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            callbacks: {
              label: (ctx) => 'F1: ' + ctx.parsed.r + '%',
            },
          },
        },
        animation: { duration: 1200, easing: 'easeOutQuart' },
      },
    });
  }
})();
