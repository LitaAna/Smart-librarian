const form = document.getElementById('book-form');
const titleInput = document.getElementById('title');
const summaryInput = document.getElementById('summary');
const originalTitleInput = document.getElementById('original-title');
const list = document.getElementById('books-list');
const count = document.getElementById('count');
const statusEl = document.getElementById('status');
const searchInput = document.getElementById('search');
const cancelButton = document.getElementById('cancel-button');
const saveButton = document.getElementById('save-button');
const formTitle = document.getElementById('form-title');

let books = [];

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.className = isError ? 'error' : 'success';
}

function resetForm() {
  form.reset();
  originalTitleInput.value = '';
  formTitle.textContent = 'Adaugă o carte';
  saveButton.textContent = 'Adaugă și indexează';
  cancelButton.classList.add('hidden');
}

function renderBooks() {
  const query = searchInput.value.trim().toLowerCase();
  const filtered = books.filter(book =>
    book.title.toLowerCase().includes(query) || book.summary.toLowerCase().includes(query)
  );

  count.textContent = `(${books.length})`;
  list.innerHTML = '';

  if (!filtered.length) {
    list.innerHTML = '<p class="empty">Nu există rezultate.</p>';
    return;
  }

  filtered.forEach(book => {
    const card = document.createElement('article');
    card.className = 'book-card';

    const h3 = document.createElement('h3');
    h3.textContent = book.title;

    const p = document.createElement('p');
    p.textContent = book.summary;

    const buttons = document.createElement('div');
    buttons.className = 'card-actions';

    const edit = document.createElement('button');
    edit.textContent = 'Editează';
    edit.className = 'secondary';
    edit.onclick = () => {
      originalTitleInput.value = book.title;
      titleInput.value = book.title;
      summaryInput.value = book.summary;
      formTitle.textContent = 'Editează cartea';
      saveButton.textContent = 'Salvează și reindexează';
      cancelButton.classList.remove('hidden');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const remove = document.createElement('button');
    remove.textContent = 'Șterge';
    remove.className = 'danger';
    remove.onclick = async () => {
      if (!confirm(`Ștergi cartea „${book.title}”?`)) return;
      const response = await fetch(`/api/books/${encodeURIComponent(book.title)}`, { method: 'DELETE' });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.detail || 'Ștergerea a eșuat.', true);
        return;
      }
      setStatus(data.message);
      await loadBooks();
    };

    buttons.append(edit, remove);
    card.append(h3, p, buttons);
    list.append(card);
  });
}

async function loadBooks() {
  try {
    const response = await fetch('/api/books');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Nu am putut încărca lista.');
    books = data.books;
    renderBooks();
  } catch (error) {
    setStatus(error.message, true);
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  setStatus('Se salvează și se reindexează...');

  const payload = {
    title: titleInput.value.trim(),
    summary: summaryInput.value.trim(),
  };
  const originalTitle = originalTitleInput.value;
  const editing = Boolean(originalTitle);
  const url = editing ? `/api/books/${encodeURIComponent(originalTitle)}` : '/api/books';
  const method = editing ? 'PUT' : 'POST';

  try {
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Salvarea a eșuat.');
    setStatus(data.message);
    resetForm();
    await loadBooks();
  } catch (error) {
    setStatus(error.message, true);
  }
});

searchInput.addEventListener('input', renderBooks);
cancelButton.addEventListener('click', resetForm);
document.getElementById('refresh-button').addEventListener('click', loadBooks);

loadBooks();
