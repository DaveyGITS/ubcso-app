/**
 * org_media.js — Org profile media interactions
 * Handles: inline album gallery toggle, showcase expander, lightbox
 */

(function () {
  'use strict';

  // ─── Lightbox state ──────────────────────────────────────────────────────
  let currentPhotos = [];
  let currentIndex = 0;

  const lightbox = document.getElementById('lightbox');
  const lbImg = document.getElementById('lb-img');
  const lbPrev = document.getElementById('lb-prev');
  const lbNext = document.getElementById('lb-next');
  const lbClose = document.getElementById('lb-close');

  function openLightbox(photos, index) {
    currentPhotos = photos;
    currentIndex = index;
    lbImg.src = photos[index];
    lightbox.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    lightbox.classList.add('hidden');
    document.body.style.overflow = '';
  }

  function showPrev() {
    currentIndex = (currentIndex - 1 + currentPhotos.length) % currentPhotos.length;
    lbImg.src = currentPhotos[currentIndex];
  }

  function showNext() {
    currentIndex = (currentIndex + 1) % currentPhotos.length;
    lbImg.src = currentPhotos[currentIndex];
  }

  if (lbPrev) lbPrev.addEventListener('click', showPrev);
  if (lbNext) lbNext.addEventListener('click', showNext);
  if (lbClose) lbClose.addEventListener('click', closeLightbox);
  if (lightbox) {
    lightbox.addEventListener('click', function (e) {
      if (e.target === lightbox) closeLightbox();
    });
  }

  // Keyboard navigation
  document.addEventListener('keydown', function (e) {
    if (!lightbox || lightbox.classList.contains('hidden')) return;
    if (e.key === 'ArrowLeft') showPrev();
    if (e.key === 'ArrowRight') showNext();
    if (e.key === 'Escape') closeLightbox();
  });

  // ─── Gallery thumb click → open lightbox ─────────────────────────────────
  function attachThumbListeners() {
    document.querySelectorAll('.gallery-thumb').forEach(function (img) {
      img.addEventListener('click', function () {
        const albumId = img.dataset.album;
        const index = parseInt(img.dataset.index, 10);
        const siblings = document.querySelectorAll(`.gallery-thumb[data-album="${albumId}"]`);
        const photos = Array.from(siblings).map(function (el) { return el.dataset.src || el.src; });
        openLightbox(photos, index);
      });
    });
  }

  attachThumbListeners();

  // ─── Inline album gallery toggle ─────────────────────────────────────────
  document.querySelectorAll('.open-album-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const albumId = btn.dataset.albumId;
      const gallery = document.getElementById('album-gallery-' + albumId);
      if (!gallery) return;
      const isHidden = gallery.classList.toggle('hidden');
      btn.textContent = isHidden ? 'View Photos' : 'Hide Photos';
      // Re-attach listeners after gallery is shown
      if (!isHidden) attachThumbListeners();
    });
  });

  // ─── Showcase expander ───────────────────────────────────────────────────
  const showcaseExpander = document.getElementById('showcase-expander');
  const showcaseGallery = document.getElementById('showcase-gallery');
  const showcaseGalleryClose = document.getElementById('showcase-gallery-close');

  if (showcaseExpander && showcaseGallery) {
    showcaseExpander.addEventListener('click', function () {
      const isHidden = showcaseGallery.classList.toggle('hidden');
      showcaseExpander.innerHTML = isHidden
        ? '<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg> View Album'
        : '<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg> Close';
    });
  }

  if (showcaseGalleryClose && showcaseGallery) {
    showcaseGalleryClose.addEventListener('click', function () {
      showcaseGallery.classList.add('hidden');
      if (showcaseExpander) {
        showcaseExpander.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg> View Album';
      }
    });
  }

})();
