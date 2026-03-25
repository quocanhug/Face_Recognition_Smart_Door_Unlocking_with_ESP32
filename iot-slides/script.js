// ==================== SLIDE ENGINE ====================
const slides = document.querySelectorAll('.slide-panel');
const navItems = document.querySelectorAll('.nav-item');
const totalSlides = slides.length;
let currentIndex = 0;

// Section mapping for sidebar
const sections = {
  'intro': { icon: 'info', label: 'Mở Đầu', slides: [0,1,2,3,4] },
  'arch': { icon: 'architecture', label: 'Kiến Trúc', slides: [5,6,7,8] },
  'hw': { icon: 'memory', label: 'Phần Cứng', slides: [9,10,11] },
  'sw': { icon: 'code', label: 'Phần Mềm', slides: [12,13,14] },
  'results': { icon: 'analytics', label: 'Kết Quả', slides: [15,16] },
  'conclusion': { icon: 'verified', label: 'Kết Luận', slides: [17,18,19] }
};

function getSectionForSlide(idx) {
  for (const [key, sec] of Object.entries(sections)) {
    if (sec.slides.includes(idx)) return key;
  }
  return null;
}

function showSlide(index) {
  if (index < 0 || index >= totalSlides) return;
  slides.forEach(s => s.classList.remove('active'));
  slides[index].classList.add('active');
  currentIndex = index;

  // Update sidebar
  const currentSection = getSectionForSlide(index);
  navItems.forEach(item => {
    item.classList.remove('active');
    if (item.dataset.section === currentSection) item.classList.add('active');
  });

  // Update counter
  const counterEl = document.getElementById('slideCounter');
  if (counterEl) counterEl.textContent = (index + 1) + '/' + totalSlides;
  const frameEl = document.getElementById('frameLabel');
  if (frameEl) frameEl.textContent = 'FRAME ' + String(index + 1).padStart(2, '0');

  // Update progress dots
  document.querySelectorAll('.progress-dot').forEach((dot, i) => {
    dot.classList.toggle('active', i === index);
  });

  // Update footer
  const footerFrame = document.getElementById('footerFrame');
  if (footerFrame) footerFrame.textContent = 'FRAME ' + String(index + 1).padStart(2, '0');

  history.replaceState(null, null, '#' + (index + 1));
}

function nextSlide() { if (currentIndex < totalSlides - 1) showSlide(currentIndex + 1); }
function prevSlide() { if (currentIndex > 0) showSlide(currentIndex - 1); }

// Keyboard
document.addEventListener('keydown', e => {
  switch (e.key) {
    case 'ArrowRight': case 'ArrowDown': case ' ': case 'PageDown':
      e.preventDefault(); nextSlide(); break;
    case 'ArrowLeft': case 'ArrowUp': case 'PageUp':
      e.preventDefault(); prevSlide(); break;
    case 'Home': e.preventDefault(); showSlide(0); break;
    case 'End': e.preventDefault(); showSlide(totalSlides - 1); break;
    case 'f': case 'F':
      e.preventDefault();
      if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(()=>{});
      else document.exitFullscreen();
      break;
  }
});

// Sidebar click
navItems.forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    const sec = item.dataset.section;
    if (sections[sec]) showSlide(sections[sec].slides[0]);
  });
});

// Click zones
document.querySelector('main')?.addEventListener('click', e => {
  if (e.target.closest('.nav-item, button, a, .img-placeholder, aside')) return;
  const x = e.clientX - (document.querySelector('aside')?.offsetWidth || 0);
  const w = document.querySelector('main')?.offsetWidth || window.innerWidth;
  if (x > w * 0.65) nextSlide();
  else if (x < w * 0.35) prevSlide();
});

// Touch swipe
let touchX = 0;
document.addEventListener('touchstart', e => { touchX = e.changedTouches[0].screenX; }, { passive: true });
document.addEventListener('touchend', e => {
  const dx = e.changedTouches[0].screenX - touchX;
  if (Math.abs(dx) > 50) { dx < 0 ? nextSlide() : prevSlide(); }
}, { passive: true });

// Mouse wheel
let wheelLock = null;
document.addEventListener('wheel', e => {
  if (wheelLock) return;
  wheelLock = setTimeout(() => wheelLock = null, 600);
  e.deltaY > 0 ? nextSlide() : prevSlide();
}, { passive: true });

// Hash nav
function loadFromHash() {
  const n = parseInt(location.hash.replace('#', ''));
  showSlide(n >= 1 && n <= totalSlides ? n - 1 : 0);
}
window.addEventListener('hashchange', loadFromHash);

// Mobile sidebar toggle
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('-translate-x-full');
}

// Init
loadFromHash();
