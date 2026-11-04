// Menú móvil
const burger = document.getElementById('burger');
if (burger) burger.addEventListener('click', () => document.getElementById('nav').classList.toggle('open'));

// Vista previa de la foto al seleccionarla
const foto = document.getElementById('foto');
if (foto) foto.addEventListener('change', () => {
  const f = foto.files[0], img = document.getElementById('preview');
  if (f) { img.src = URL.createObjectURL(f); img.hidden = false; }
});

// Confirmar antes de desactivar
document.querySelectorAll('form[action$="/toggle"]').forEach(form =>
  form.addEventListener('submit', e => {
    const t = form.querySelector('button').textContent.trim();
    if (t === 'Desactivar' && !confirm('¿Desactivar esta credencial?')) e.preventDefault();
  }));
