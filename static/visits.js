const consent = document.getElementById('gps-consent');
const status = document.getElementById('gps-status');
consent.addEventListener('change', () => {
  if (!consent.checked) {
    document.getElementById('latitude').value = '';
    document.getElementById('longitude').value = '';
    status.textContent = 'Location removed from this visit.';
  }
});
document.getElementById('capture-gps').addEventListener('click', () => {
  if (!consent.checked) { status.textContent = 'Give consent before capturing location.'; return; }
  if (!navigator.geolocation) { status.textContent = 'Location is unavailable; you can still record the visit.'; return; }
  navigator.geolocation.getCurrentPosition(position => {
    if (!consent.checked) return;
    document.getElementById('latitude').value = position.coords.latitude.toFixed(6);
    document.getElementById('longitude').value = position.coords.longitude.toFixed(6);
    status.textContent = 'Location captured for this visit.';
  }, () => { status.textContent = 'Location permission denied or unavailable. You can still record the visit.'; }, {timeout:10000});
});
