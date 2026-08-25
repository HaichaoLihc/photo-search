document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const searchInput = document.getElementById('search-input');
  const clearBtn = document.getElementById('clear-btn');
  const searchBtn = document.getElementById('search-btn');
  const thresholdSlider = document.getElementById('threshold-slider');
  const thresholdVal = document.getElementById('threshold-val');
  const limitSelect = document.getElementById('limit-select');
  const resultsGrid = document.getElementById('results-grid');
  const resultsCount = document.getElementById('results-count');
  const latencyTag = document.getElementById('latency-tag');
  const loadingSpinner = document.getElementById('loading-spinner');
  const emptyState = document.getElementById('empty-state');
  
  // Header Stats Elements
  const backendStatusText = document.getElementById('backend-status-text');
  const indexedCountText = document.getElementById('indexed-count-text');
  const deviceTag = document.getElementById('device-tag');
  const reloadIndexBtn = document.getElementById('reload-index-btn');
  
  // View Toggles
  const gridSizeSm = document.getElementById('grid-size-sm');
  const gridSizeMd = document.getElementById('grid-size-md');
  
  // Lightbox Modal Elements
  const lightboxModal = document.getElementById('lightbox-modal');
  const lightboxBackdrop = document.getElementById('lightbox-backdrop');
  const lightboxClose = document.getElementById('lightbox-close');
  const lightboxPrev = document.getElementById('lightbox-prev');
  const lightboxNext = document.getElementById('lightbox-next');
  const lightboxImg = document.getElementById('lightbox-img');
  const lightboxRankBadge = document.getElementById('lightbox-rank-badge');
  const lightboxScoreBadge = document.getElementById('lightbox-score-badge');
  const lightboxFilename = document.getElementById('lightbox-filename');
  const lightboxRawScore = document.getElementById('lightbox-raw-score');
  const lightboxScoreFill = document.getElementById('lightbox-score-fill');
  const lightboxFolder = document.getElementById('lightbox-folder');
  const lightboxPath = document.getElementById('lightbox-path');
  const lightboxQueryMatched = document.getElementById('lightbox-query-matched');
  const lightboxOpenRaw = document.getElementById('lightbox-open-raw');
  const copyPathBtn = document.getElementById('copy-path-btn');
  const copyPhotoBtn = document.getElementById('copy-photo-btn');
  const toast = document.getElementById('toast');
  const toastMessage = document.getElementById('toast-message');

  // Load More Elements
  const loadMoreContainer = document.getElementById('load-more-container');
  const loadMoreBtn = document.getElementById('load-more-btn');
  const loadMoreText = document.getElementById('load-more-text');
  const loadMoreSpinner = document.getElementById('load-more-spinner');

  // Application State
  let currentResults = [];
  let currentQuery = "";
  let activeLightboxIndex = 0;
  let searchDebounceTimer = null;
  let currentLimit = 24;



  // Initialize App
  fetchStats();

  // Search Input Event Listeners
  searchInput.addEventListener('input', () => {
    const val = searchInput.value.trim();
    if (val.length > 0) {
      clearBtn.classList.remove('hidden');
    } else {
      clearBtn.classList.add('hidden');
    }

    // Live search debounced
    clearTimeout(searchDebounceTimer);
    if (val.length >= 2) {
      searchDebounceTimer = setTimeout(() => {
        performSearch(val);
      }, 350);
    } else if (val.length === 0) {
      clearResults();
    }
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      clearTimeout(searchDebounceTimer);
      const val = searchInput.value.trim();
      if (val) performSearch(val);
    }
  });

  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearBtn.classList.add('hidden');
    searchInput.focus();
    clearResults();
  });

  searchBtn.addEventListener('click', () => {
    const val = searchInput.value.trim();
    if (val) performSearch(val);
  });

  // Example Prompt Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.query;
      searchInput.value = q;
      clearBtn.classList.remove('hidden');
      performSearch(q);
    });
  });

  // Controls Event Listeners
  thresholdSlider.addEventListener('input', () => {
    thresholdVal.textContent = `${thresholdSlider.value}%`;
    if (currentQuery) performSearch(currentQuery);
  });

  limitSelect.addEventListener('change', () => {
    if (currentQuery) performSearch(currentQuery);
  });

  // Grid Size Toggles
  gridSizeSm.addEventListener('click', () => {
    gridSizeSm.classList.add('active');
    gridSizeMd.classList.remove('active');
    resultsGrid.classList.remove('grid-md');
    resultsGrid.classList.add('grid-sm');
  });

  gridSizeMd.addEventListener('click', () => {
    gridSizeMd.classList.add('active');
    gridSizeSm.classList.remove('active');
    resultsGrid.classList.remove('grid-sm');
    resultsGrid.classList.add('grid-md');
  });

  if (reloadIndexBtn) {
    reloadIndexBtn.addEventListener('click', async () => {
      try {
        reloadIndexBtn.disabled = true;
        reloadIndexBtn.textContent = 'Reloading...';
        const res = await fetch('/api/reload', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          showToast(`Index reloaded: ${data.total_images} photos indexed.`);
          fetchStats();
          if (currentQuery) performSearch(currentQuery);
        } else {
          showToast('Failed to reload index file.');
        }
      } catch (err) {
        showToast('Error reloading index.');
      } finally {
        reloadIndexBtn.disabled = false;
        reloadIndexBtn.textContent = 'Reload Index';
      }
    });
  }

  // API Call: Fetch Stats
  async function fetchStats() {
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        const data = await res.json();
        indexedCountText.textContent = `${data.total_images.toLocaleString()} Photos Indexed`;
        deviceTag.textContent = (data.device || 'CPU').toUpperCase();
        backendStatusText.textContent = 'AI Engine Active';
      }
    } catch (err) {
      console.warn('Backend server connecting...', err);
      backendStatusText.textContent = 'Connecting to Engine...';
    }
  }

  // API Call: Perform Search
  async function performSearch(query, isLoadMore = false) {
    if (!isLoadMore) {
      currentQuery = query;
      currentLimit = parseInt(limitSelect.value, 10);
      showLoading(true);
    } else {
      currentLimit += parseInt(limitSelect.value, 10);
      setLoadMoreBtnLoading(true);
    }

    emptyState.classList.add('hidden');

    try {
      const threshold = parseFloat(thresholdSlider.value) / 100.0;
      const url = `/api/search?q=${encodeURIComponent(query)}&k=${currentLimit}&threshold=${threshold}`;
      const res = await fetch(url);

      if (!res.ok) {
        throw new Error(`Search error (${res.status})`);
      }

      const data = await res.json();
      const newResults = data.results || [];
      const prevLength = isLoadMore ? currentResults.length : 0;
      currentResults = newResults;

      renderResults(currentResults, data.execution_time_ms, isLoadMore, prevLength);

      // Load More Button state update
      if (currentResults.length > 0) {
        loadMoreContainer.classList.remove('hidden');
        if (currentResults.length < currentLimit) {
          loadMoreBtn.disabled = true;
          loadMoreText.textContent = `All ${currentResults.length} matching photos loaded`;
        } else {
          loadMoreBtn.disabled = false;
          loadMoreText.textContent = `Load More Results (+${limitSelect.value})`;
        }
      } else {
        loadMoreContainer.classList.add('hidden');
      }
    } catch (err) {
      console.error('Search request failed:', err);
      resultsCount.textContent = 'Search failed. Is backend server running?';
      latencyTag.classList.add('hidden');
      if (!isLoadMore) resultsGrid.innerHTML = '';
    } finally {
      showLoading(false);
      setLoadMoreBtnLoading(false);
    }
  }

  function setLoadMoreBtnLoading(isLoading) {
    if (!loadMoreBtn) return;
    if (isLoading) {
      loadMoreBtn.disabled = true;
      loadMoreSpinner.classList.remove('hidden');
      loadMoreText.textContent = 'Loading more photos...';
    } else {
      loadMoreSpinner.classList.add('hidden');
    }
  }

  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', () => {
      if (currentQuery) {
        performSearch(currentQuery, true);
      }
    });
  }

  function showLoading(isLoading) {
    if (isLoading) {
      loadingSpinner.classList.remove('hidden');
      resultsGrid.classList.add('hidden');
    } else {
      loadingSpinner.classList.add('hidden');
      resultsGrid.classList.remove('hidden');
    }
  }

  function clearResults() {
    currentQuery = '';
    currentResults = [];
    resultsGrid.innerHTML = '';
    emptyState.classList.remove('hidden');
    resultsCount.textContent = 'Ready to search';
    latencyTag.classList.add('hidden');
    if (loadMoreContainer) loadMoreContainer.classList.add('hidden');
  }

  // Render Grid Results Cards
  function renderResults(results, latencyMs, isLoadMore = false, startIndex = 0) {
    if (!isLoadMore) {
      resultsGrid.innerHTML = '';
    }

    if (!results || results.length === 0) {
      emptyState.classList.remove('hidden');
      resultsCount.textContent = 'No matching photos found';
      latencyTag.classList.add('hidden');
      if (loadMoreContainer) loadMoreContainer.classList.add('hidden');
      return;
    }

    emptyState.classList.add('hidden');
    resultsCount.textContent = `Showing ${results.length} matching photos`;
    latencyTag.textContent = `${latencyMs} ms`;
    latencyTag.classList.remove('hidden');

    const itemsToRender = isLoadMore ? results.slice(startIndex) : results;

    itemsToRender.forEach((item, idxOffset) => {
      const idx = isLoadMore ? startIndex + idxOffset : idxOffset;
      const card = document.createElement('div');
      card.className = 'photo-card';
      card.dataset.index = idx;

      const imgUrl = `/api/image?path=${encodeURIComponent(item.path)}`;

      card.innerHTML = `
        <img src="${imgUrl}" alt="${escapeHtml(item.filename)}" loading="lazy" />
        <div class="card-overlay">
          <div class="card-top">
            <span class="rank-badge">#${item.rank}</span>
            <span class="score-badge">${item.score_percentage}% Match</span>
          </div>
          <div class="card-bottom">
            <div class="card-filename">${escapeHtml(item.filename)}</div>
            <div class="card-folder">${escapeHtml(item.parent_dir)}</div>
          </div>
        </div>
      `;

      card.addEventListener('click', () => openLightbox(idx));

      const img = card.querySelector('img');
      if (img) {
        img.onload = () => {
          if (img.naturalWidth && img.naturalHeight) {
            const ratio = img.naturalWidth / img.naturalHeight;
            const baseHeight = resultsGrid.classList.contains('grid-sm') ? 180 : 250;
            const calcWidth = Math.round(baseHeight * ratio);
            card.style.flex = `${ratio.toFixed(3)} ${ratio.toFixed(3)} ${calcWidth}px`;
            card.style.aspectRatio = `${img.naturalWidth} / ${img.naturalHeight}`;
          }
        };
      }

      resultsGrid.appendChild(card);
    });
  }



  // Lightbox Modal Controls
  function openLightbox(index) {
    if (index < 0 || index >= currentResults.length) return;
    activeLightboxIndex = index;
    const item = currentResults[activeLightboxIndex];

    const imgUrl = `/api/image?path=${encodeURIComponent(item.path)}`;
    lightboxImg.src = imgUrl;

    lightboxRankBadge.textContent = `#${item.rank} Top Match`;
    lightboxScoreBadge.textContent = `${item.score_percentage}% Match`;
    lightboxFilename.textContent = item.filename;
    lightboxRawScore.textContent = item.score.toFixed(4);
    lightboxScoreFill.style.width = `${Math.min(100, Math.max(0, item.score_percentage))}%`;
    lightboxFolder.textContent = item.parent_dir;
    lightboxPath.textContent = item.path;
    lightboxQueryMatched.textContent = `"${currentQuery}"`;
    lightboxOpenRaw.href = imgUrl;

    lightboxModal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    lightboxModal.classList.add('hidden');
    lightboxImg.src = '';
    document.body.style.overflow = '';
  }

  function prevLightbox() {
    if (currentResults.length === 0) return;
    let nextIdx = activeLightboxIndex - 1;
    if (nextIdx < 0) nextIdx = currentResults.length - 1;
    openLightbox(nextIdx);
  }

  function nextLightbox() {
    if (currentResults.length === 0) return;
    let nextIdx = activeLightboxIndex + 1;
    if (nextIdx >= currentResults.length) nextIdx = 0;
    openLightbox(nextIdx);
  }

  lightboxClose.addEventListener('click', closeLightbox);
  lightboxBackdrop.addEventListener('click', closeLightbox);
  lightboxPrev.addEventListener('click', prevLightbox);
  lightboxNext.addEventListener('click', nextLightbox);

  // Copy Path Button
  copyPathBtn.addEventListener('click', () => {
    const pathText = lightboxPath.textContent;
    if (pathText) {
      navigator.clipboard.writeText(pathText).then(() => {
        showToast('Absolute file path copied to clipboard!');
      }).catch(err => {
        console.error('Failed to copy text', err);
      });
    }
  });

  // Copy Photo Binary Button
  if (copyPhotoBtn) {
    copyPhotoBtn.addEventListener('click', () => {
      const item = currentResults[activeLightboxIndex];
      if (item) {
        const imgUrl = `/api/image?path=${encodeURIComponent(item.path)}`;
        copyImageToClipboard(imgUrl);
      }
    });
  }

  async function copyImageToClipboard(imageUrl) {
    showToast('Copying photo image to clipboard...');
    try {
      const response = await fetch(imageUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();

      // Convert to PNG blob if needed (ClipboardItem requires image/png in web browsers)
      let pngBlob = blob;
      if (blob.type !== 'image/png') {
        pngBlob = await convertBlobToPng(blob);
      }

      if (navigator.clipboard && window.ClipboardItem) {
        const item = new ClipboardItem({ [pngBlob.type]: pngBlob });
        await navigator.clipboard.write([item]);
        showToast('Photo image copied to clipboard! 📋');
      } else {
        throw new Error('ClipboardItem API not supported in browser');
      }
    } catch (err) {
      console.warn('Failed to copy photo binary directly:', err);
      // Fallback: Copy absolute file path if direct binary copy fails
      const item = currentResults[activeLightboxIndex];
      if (item && item.path) {
        navigator.clipboard.writeText(item.path);
        showToast('Direct image copy restricted; copied file path instead!');
      } else {
        showToast('Could not copy photo to clipboard.');
      }
    }
  }

  function convertBlobToPng(blob) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth || img.width;
        canvas.height = img.naturalHeight || img.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        canvas.toBlob((pngBlob) => {
          if (pngBlob) resolve(pngBlob);
          else reject(new Error('Canvas toBlob failed'));
        }, 'image/png');
      };
      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        reject(e);
      };
      img.src = url;
    });
  }

  function showToast(msg) {
    toastMessage.textContent = msg;
    toast.classList.remove('hidden');
    setTimeout(() => {
      toast.classList.add('hidden');
    }, 3000);
  }

  // Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    if (!lightboxModal.classList.contains('hidden')) {
      if (e.key === 'Escape') closeLightbox();
      if (e.key === 'ArrowLeft') prevLightbox();
      if (e.key === 'ArrowRight') nextLightbox();
      if (e.key.toLowerCase() === 'c' && !e.metaKey && !e.ctrlKey) {
        const item = currentResults[activeLightboxIndex];
        if (item) {
          const imgUrl = `/api/image?path=${encodeURIComponent(item.path)}`;
          copyImageToClipboard(imgUrl);
        }
      }
    } else {
      // Shortcut '/' to focus search input
      if (e.key === '/' && document.activeElement !== searchInput) {
        e.preventDefault();
        searchInput.focus();
      }
    }
  });


  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, function(m) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      }[m];
    });
  }
});
