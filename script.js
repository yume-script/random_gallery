(function () {
  console.log('[Random-Gallery-Plugin] Category-Level Fullpage UI loaded.');

  let allItems = [];
  let categories = [];
  let activeCategory = '__all__';

  function fetchGalleryData() {
    const grid = document.getElementById('rg-grid');
    const status = document.getElementById('rg-status');
    if (!grid || !status) return;

    status.textContent = '이미지를 불러오는 중...';
    status.style.display = 'block';
    grid.innerHTML = '';

    fetch('/api/media/dashboard/widgets/random_gallery/data?type=general&limit=100')
      .then((res) => res.json())
      .then((data) => {
        if (!data.success) {
          status.textContent = '이미지를 가져오지 못했습니다: ' + (data.error || '알 수 없는 오류');
          status.style.display = 'block';
          return;
        }
        allItems = Array.isArray(data.items) ? data.items : [];
        categories = Array.isArray(data.categories) ? data.categories : [];
        renderCategoryButtons();
        renderGrid();
      })
      .catch((err) => {
        console.error('[Random-Gallery-Plugin] fetch failed:', err);
        status.textContent = '서버 연결 오류';
        status.style.display = 'block';
      });
  }

  function renderCategoryButtons() {
    const row = document.getElementById('rg-category-row');
    if (!row) return;
    row.innerHTML = '';

    // 유니크한 카테고리만 사용 (동일 라벨 중복 방지)
    const uniqueCategories = Array.from(new Set(categories));

    if (uniqueCategories.length <= 1) {
      row.style.display = 'none';
      return;
    }
    row.style.display = 'flex';

    const makeBtn = (label, value) => {
      const btn = document.createElement('button');
      btn.className = 'rg-cat-btn' + (activeCategory === value ? ' active' : '');
      btn.textContent = label;
      btn.dataset.category = value;
      btn.addEventListener('click', () => {
        activeCategory = value;
        row.querySelectorAll('.rg-cat-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        renderGrid();
      });
      return btn;
    };

    row.appendChild(makeBtn('전체', '__all__'));
    uniqueCategories.forEach((cat) => row.appendChild(makeBtn(cat, cat)));
  }

  function renderGrid() {
    const grid = document.getElementById('rg-grid');
    const status = document.getElementById('rg-status');
    if (!grid || !status) return;
    grid.innerHTML = '';

    const filtered =
      activeCategory === '__all__' ? allItems : allItems.filter((it) => it.category === activeCategory);

    if (filtered.length === 0) {
      status.textContent = '표시할 이미지가 없습니다.';
      status.style.display = 'block';
      return;
    }
    status.style.display = 'none';

    filtered.forEach((item) => {
      const cell = document.createElement('a');
      cell.className = 'rg-cell';
      cell.href = item.link || item.image || item.cover || '#';
      cell.target = '_blank';
      cell.rel = 'noopener noreferrer';

      const img = document.createElement('img');
      img.src = item.image || item.cover || item.image_url || '';
      img.alt = item.title || '';
      img.loading = 'lazy';
      cell.appendChild(img);

      if (item.category) {
        const badge = document.createElement('span');
        badge.className = 'rg-badge';
        badge.textContent = item.category;
        cell.appendChild(badge);
      }

      grid.appendChild(cell);
    });
  }

  const shuffleBtn = document.getElementById('rg-shuffle-btn');
  if (shuffleBtn) {
    shuffleBtn.addEventListener('click', fetchGalleryData);
  }

  fetchGalleryData();
})();
