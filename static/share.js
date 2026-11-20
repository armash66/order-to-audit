// Native file sharing attaches the PDF; desktop users can download and attach it.
document.querySelectorAll('[data-share-pdf]').forEach(button => {
  button.addEventListener('click', async () => {
    try {
      const response = await fetch(button.dataset.sharePdf);
      if (!response.ok) throw new Error('PDF download failed');
      const file = new File([await response.blob()], 'invoice.pdf', {type: 'application/pdf'});
      if (navigator.canShare && navigator.canShare({files: [file]})) {
        await navigator.share({files: [file], title: 'Tax invoice'});
      } else {
        document.getElementById('share-help').hidden = false;
      }
    } catch (error) {
      if (error.name !== 'AbortError') document.getElementById('share-help').hidden = false;
    }
  });
});
