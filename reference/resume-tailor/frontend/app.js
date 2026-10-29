/**
 * Resume Tailor — Frontend Client Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const resumeInput = document.getElementById('resume-input');
  const jobInput = document.getElementById('job-input');
  const resumeCount = document.getElementById('resume-count');
  const jobCount = document.getElementById('job-count');
  const resumeClear = document.getElementById('resume-clear');
  const jobClear = document.getElementById('job-clear');
  const sampleBtn = document.getElementById('sample-btn');

  const tailorBtn = document.getElementById('tailor-btn');
  const tailorSpinner = document.getElementById('tailor-spinner');
  const tailorIcon = document.getElementById('tailor-icon');
  const tailorBtnText = document.getElementById('tailor-btn-text');

  const alertBanner = document.getElementById('alert-banner');
  const alertMessage = document.getElementById('alert-message');
  const alertClose = document.getElementById('alert-close');

  const resultsCountBadge = document.getElementById('results-count-badge');
  const copyAllBtn = document.getElementById('copy-all-btn');
  const summaryInsight = document.getElementById('summary-insight');
  const insightText = document.getElementById('insight-text');
  const resultsContainer = document.getElementById('results-container');
  const emptyState = document.getElementById('empty-state');
  const skeletonLoader = document.getElementById('skeleton-loader');

  // State
  let currentBullets = [];

  // Realistic Sample Data for 1-click test
  const SAMPLE_RESUME = `• Built backend APIs using Python and FastAPI for customer-facing web services.
• Improved database queries in PostgreSQL so endpoints loaded faster.
• Managed container deployments using Docker and GitHub Actions CI/CD pipelines.`;

  const SAMPLE_JOB = `Senior Backend Engineer — Cloud Services
We are seeking a Backend Engineer with strong expertise in Python, FastAPI, and PostgreSQL.
Responsibilities:
- Architect and scale low-latency distributed REST services handling high concurrency.
- Profile and optimize relational database schema, indexing, and query performance.
- Champion automated testing (pytest), CI/CD pipelines, and cloud reliability best practices.`;

  // Update Character Counters
  function updateCounters() {
    resumeCount.textContent = `${resumeInput.value.length.toLocaleString()} / 10,000`;
    jobCount.textContent = `${jobInput.value.length.toLocaleString()} / 10,000`;
  }

  resumeInput.addEventListener('input', updateCounters);
  jobInput.addEventListener('input', updateCounters);

  // Clear Handlers
  resumeClear.addEventListener('click', () => {
    resumeInput.value = '';
    updateCounters();
    resumeInput.focus();
  });

  jobClear.addEventListener('click', () => {
    jobInput.value = '';
    updateCounters();
    jobInput.focus();
  });

  // Try Sample Button
  sampleBtn.addEventListener('click', () => {
    resumeInput.value = SAMPLE_RESUME;
    jobInput.value = SAMPLE_JOB;
    updateCounters();
    hideAlert();
    resumeInput.classList.add('flash-highlight');
    jobInput.classList.add('flash-highlight');
    setTimeout(() => {
      resumeInput.classList.remove('flash-highlight');
      jobInput.classList.remove('flash-highlight');
    }, 400);
  });

  // Alert Banner Helpers
  function showAlert(message) {
    alertMessage.textContent = message;
    alertBanner.classList.remove('hidden');
    alertBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideAlert() {
    alertBanner.classList.add('hidden');
    alertMessage.textContent = '';
  }

  alertClose.addEventListener('click', hideAlert);

  // Loading State Helper
  function setLoading(isLoading) {
    tailorBtn.disabled = isLoading;
    resumeInput.readOnly = isLoading;
    jobInput.readOnly = isLoading;

    if (isLoading) {
      tailorSpinner.classList.remove('hidden');
      tailorIcon.classList.add('hidden');
      tailorBtnText.textContent = 'Tailoring Bullets...';
      emptyState.classList.add('hidden');
      skeletonLoader.classList.remove('hidden');
      clearRenderedCards();
      copyAllBtn.classList.add('hidden');
      resultsCountBadge.classList.add('hidden');
      summaryInsight.classList.add('hidden');
    } else {
      tailorSpinner.classList.add('hidden');
      tailorIcon.classList.remove('hidden');
      tailorBtnText.textContent = 'Tailor Bullets ✨';
      skeletonLoader.classList.add('hidden');
    }
  }

  function clearRenderedCards() {
    const existingCards = resultsContainer.querySelectorAll('.bullet-card');
    existingCards.forEach((c) => c.remove());
  }

  // Copy helper with clipboard API + fallback
  async function copyToClipboard(text, btnElement, successText = 'Copied!') {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const tempArea = document.createElement('textarea');
        tempArea.value = text;
        tempArea.style.position = 'fixed';
        tempArea.style.left = '-999999px';
        document.body.appendChild(tempArea);
        tempArea.focus();
        tempArea.select();
        document.execCommand('copy');
        document.body.removeChild(tempArea);
      }

      // Visual Confirmation
      const origHtml = btnElement.innerHTML;
      btnElement.classList.add('copied');
      btnElement.innerHTML = `<span>✓</span> <span>${successText}</span>`;

      setTimeout(() => {
        btnElement.classList.remove('copied');
        btnElement.innerHTML = origHtml;
      }, 2000);
    } catch (err) {
      console.error('Copy failed:', err);
      showAlert('Could not copy to clipboard. Please copy manually.');
    }
  }

  // Render Tailored Cards
  function renderBullets(data) {
    clearRenderedCards();
    currentBullets = data.bullets || [];

    if (currentBullets.length === 0) {
      emptyState.classList.remove('hidden');
      return;
    }

    emptyState.classList.add('hidden');
    resultsCountBadge.textContent = `${currentBullets.length} Bullets`;
    resultsCountBadge.classList.remove('hidden');
    copyAllBtn.classList.remove('hidden');

    if (data.summary_insight) {
      insightText.textContent = data.summary_insight;
      summaryInsight.classList.remove('hidden');
    } else {
      summaryInsight.classList.add('hidden');
    }

    currentBullets.forEach((bullet, index) => {
      const card = document.createElement('div');
      card.className = 'bullet-card';
      card.style.animationDelay = `${index * 60}ms`;

      // Top row (bullet text + copy button)
      const topRow = document.createElement('div');
      topRow.className = 'bullet-card-top';

      const bulletText = document.createElement('p');
      bulletText.className = 'bullet-text';
      bulletText.textContent = bullet.tailored_bullet;

      const copyBtn = document.createElement('button');
      copyBtn.className = 'btn-copy-card';
      copyBtn.setAttribute('title', 'Copy this bullet');
      copyBtn.innerHTML = `<span>📋</span> <span>Copy</span>`;
      copyBtn.addEventListener('click', () => {
        copyToClipboard(bullet.tailored_bullet, copyBtn, 'Copied!');
      });

      topRow.appendChild(bulletText);
      topRow.appendChild(copyBtn);
      card.appendChild(topRow);

      // Bottom meta row (impact metric tag + keyword tags)
      const metaRow = document.createElement('div');
      metaRow.className = 'bullet-meta';

      if (bullet.impact_metric_type) {
        const metricTag = document.createElement('span');
        metricTag.className = 'metric-tag';
        metricTag.textContent = `🎯 ${bullet.impact_metric_type}`;
        metaRow.appendChild(metricTag);
      }

      if (Array.isArray(bullet.matched_keywords)) {
        bullet.matched_keywords.forEach((kw) => {
          const kwTag = document.createElement('span');
          kwTag.className = 'keyword-tag';
          kwTag.textContent = `⚡ ${kw}`;
          metaRow.appendChild(kwTag);
        });
      }

      card.appendChild(metaRow);
      resultsContainer.appendChild(card);
    });
  }

  // Copy All Action
  copyAllBtn.addEventListener('click', () => {
    if (!currentBullets || currentBullets.length === 0) return;
    const formatted = currentBullets
      .map((b) => `• ${b.tailored_bullet}`)
      .join('\n\n');
    copyToClipboard(formatted, copyAllBtn, 'All Copied!');
  });

  // Submit Handler
  async function handleTailor() {
    const resume = resumeInput.value.trim();
    const job = jobInput.value.trim();

    hideAlert();

    if (resume.length < 10) {
      showAlert('Please paste your existing resume bullets (at least 10 characters).');
      resumeInput.focus();
      return;
    }

    if (job.length < 10) {
      showAlert('Please paste the target job description (at least 10 characters).');
      jobInput.focus();
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('/api/tailor', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          resume_text: resume,
          job_text: job,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to tailor bullets. Please try again.');
      }

      renderBullets(data);
    } catch (err) {
      console.error('Tailor error:', err);
      showAlert(err.message || 'Network error occurred. Please check your connection.');
      emptyState.classList.remove('hidden');
    } finally {
      setLoading(false);
    }
  }

  tailorBtn.addEventListener('click', handleTailor);

  // Keyboard shortcut: Cmd/Ctrl + Enter
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleTailor();
    }
  });

  // Initialize
  updateCounters();
});
