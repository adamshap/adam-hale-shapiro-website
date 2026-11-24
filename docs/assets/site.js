/* Progressive enhancement: every page and download also works without JS. */
document.documentElement.classList.add('js');
const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#site-nav');
if (menuButton && navigation) {
  const setMenu = (open) => {
    menuButton.setAttribute('aria-expanded', String(open));
    navigation.toggleAttribute('data-open', open);
  };
  menuButton.addEventListener('click', () => setMenu(menuButton.getAttribute('aria-expanded') !== 'true'));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') {
      setMenu(false);
      menuButton.focus();
    }
  });
  navigation.addEventListener('click', (event) => { if (event.target.closest('a')) setMenu(false); });
}
const searchInput = document.querySelector('[data-search-input]');
if (searchInput) {
  const items = [...document.querySelectorAll('[data-search-item]')];
  const groups = [...document.querySelectorAll('[data-search-group]')];
  const status = document.querySelector('[data-search-status]');
  const empty = document.querySelector('[data-empty-results]');
  const normalize = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const index = items.map((item) => normalize(item.dataset.search || item.textContent));
  const filter = () => {
    const terms = normalize(searchInput.value).trim().split(/\s+/).filter(Boolean);
    let count = 0;
    items.forEach((item, i) => {
      const matches = terms.every((term) => index[i].includes(term));
      item.hidden = !matches;
      if (matches) count += 1;
    });
    groups.forEach((group) => { group.hidden = ![...group.querySelectorAll('[data-search-item]')].some((item) => !item.hidden); });
    if (status) status.textContent = `${count} ${count === 1 ? 'result' : 'results'}`;
    if (empty) empty.hidden = count !== 0;
  };
  searchInput.addEventListener('input', filter);
  searchInput.addEventListener('search', filter);
  document.querySelector('[data-clear-search]')?.addEventListener('click', () => {
    searchInput.value = '';
    filter();
    searchInput.focus();
  });
  filter();
}
