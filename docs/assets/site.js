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

// Reveal contact details only after a visitor activates the button.
// This deters simple address harvesters; it is not access control.
for (const button of document.querySelectorAll('[data-reveal-email]')) {
  button.hidden = false;
  button.addEventListener('click', () => {
    const address = [58, 63, 58, 54, 117, 40, 51, 58, 43, 50, 41, 52, 27, 40, 61, 117, 61, 41, 57, 117, 52, 41, 60].map((value) => String.fromCharCode(value ^ 91)).join('');
    const link = document.createElement('a');
    link.className = 'revealed-email';
    link.textContent = address;
    link.href = ['mail', 'to', ':'].join('') + address;
    button.replaceWith(link);
    link.focus();
  }, { once: true });
}

// Topic filters preserve the original order of papers and Economic Letters.
const topicButtons = [...document.querySelectorAll('[data-topic]')];
if (topicButtons.length) {
  const papers = [...document.querySelectorAll('[data-topics]')];
  const groups = [...document.querySelectorAll('.research-group')];
  topicButtons.forEach((button) => button.addEventListener('click', () => {
    const topic = button.dataset.topic;
    topicButtons.forEach((tab) => tab.setAttribute('aria-pressed', String(tab === button)));
    papers.forEach((paper) => {
      paper.hidden = topic !== 'all' && !paper.dataset.topics.split(' ').includes(topic);
    });
    groups.forEach((group) => {
      group.hidden = ![...group.querySelectorAll('[data-topics]')].some((paper) => !paper.hidden);
    });
  }));
}

// Read freshness from the same public CSV files used by the dashboards.
const monthFormat = new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const updatedFormat = new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
async function updateDashboardFreshness(note) {
  try {
    const response = await fetch(note.dataset.dashboardUpdated, { cache: 'no-cache' });
    if (!response.ok) throw new Error('Dashboard data unavailable');
    const csv = await response.text();
    let latestMonth = null;
    for (const line of csv.split(/\r?\n/)) {
      const comma = line.indexOf(',');
      if (comma < 0 || !line.slice(comma + 1).replace(/[,"\s]/g, '')) continue;
      const match = line.slice(0, comma).trim().replace(/^"|"$/g, '').match(/^(\d{4})(?:-|m)(\d{1,2})(?:-\d{2})?$/);
      if (!match) continue;
      const year = Number(match[1]), month = Number(match[2]);
      if (year < 1900 || month < 1 || month > 12) continue;
      const date = Date.UTC(year, month - 1, 1);
      if (latestMonth === null || date > latestMonth) latestMonth = date;
    }
    if (latestMonth === null) throw new Error('No dashboard dates found');
    const modified = new Date(response.headers.get('Last-Modified') || '');
    const parts = [];
    if (Number.isFinite(modified.getTime())) parts.push(`Updated ${updatedFormat.format(modified)}`);
    parts.push(`Data through ${monthFormat.format(latestMonth)}`);
    note.textContent = parts.join(' \u00b7 ');
    note.hidden = false;
  } catch {
    note.textContent = 'See dashboard for the latest data.';
    note.hidden = false;
  }
}
document.querySelectorAll('[data-dashboard-updated]').forEach(updateDashboardFreshness);
