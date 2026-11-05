// Menú móvil
const burger = document.getElementById('burger');
if (burger) burger.addEventListener('click', () => document.getElementById('nav').classList.toggle('open'));

// Selector de fotografía con vista previa, validación y arrastrar/soltar
const foto = document.getElementById('foto');
const dropzone = document.getElementById('dropzone');
const preview = document.getElementById('preview');
const previewEmpty = document.getElementById('preview-empty');
const fileName = document.getElementById('file-name');

function mostrarArchivo(f) {
  if (!f) return;
  const okTypes = ['image/png', 'image/jpeg', 'image/webp'];
  if (!okTypes.includes(f.type)) {
    alert('Formato no permitido. Selecciona una imagen PNG, JPG o WEBP.');
    foto.value = '';
    return;
  }
  if (f.size > 4 * 1024 * 1024) {
    alert('La imagen supera el límite máximo de 4 MB.');
    foto.value = '';
    return;
  }
  preview.src = URL.createObjectURL(f);
  preview.hidden = false;
  if (previewEmpty) previewEmpty.hidden = true;
  if (fileName) {
    const kb = Math.max(1, Math.round(f.size / 1024));
    fileName.textContent = `✓ ${f.name} (${kb} KB)`;
    fileName.classList.add('ok');
    fileName.classList.remove('err');
  }
}

if (foto) {
  foto.addEventListener('change', () => mostrarArchivo(foto.files[0]));
  foto.addEventListener('invalid', () => {
    if (fileName) {
      fileName.textContent = '! Debes elegir una fotografía del trabajador';
      fileName.classList.add('err');
    }
    if (dropzone) dropzone.classList.add('shake');
  });
}

if (dropzone && foto) {
  ['dragenter', 'dragover'].forEach(ev =>
    dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add('drag'); })
  );
  ['dragleave', 'drop'].forEach(ev =>
    dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove('drag'); })
  );
  dropzone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files && files.length) {
      foto.files = files;
      mostrarArchivo(files[0]);
    }
  });
}

// Convertir CURP automáticamente a mayúsculas
const curp = document.getElementById('curp');
if (curp) curp.addEventListener('input', () => { curp.value = curp.value.toUpperCase().replace(/[^A-Z0-9]/g, ''); });

// Sincronizar fecha mínima de vencimiento con fecha de inicio
const fIni = document.getElementById('fecha_inicio');
const fVen = document.getElementById('fecha_vencimiento');
if (fIni && fVen) {
  const syncMin = () => { if (fIni.value) fVen.min = fIni.value; };
  fIni.addEventListener('change', syncMin);
  syncMin();
}

// Confirmar antes de desactivar
document.querySelectorAll('form[action$="/toggle"]').forEach(form =>
  form.addEventListener('submit', e => {
    const t = form.querySelector('button').textContent.trim();
    if (t === 'Desactivar' && !confirm('¿Desactivar esta credencial?')) e.preventDefault();
  }));
