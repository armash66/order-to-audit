const orderForm = document.getElementById('order-form');
if (orderForm) {
  const customer = orderForm.querySelector('[name=customer]');
  let requestNumber = 0;
  async function refreshPrices() {
    const current = ++requestNumber;
    try {
      const response = await fetch(`/customers/${customer.value}/prices/`);
      if (!response.ok) return;
      const data = await response.json();
      if (current !== requestNumber) return;
      orderForm.querySelectorAll('[name=sku]').forEach(select => {
        const value = select.value;
        select.replaceChildren();
        data.products.forEach(product => select.add(new Option(product.name, product.id)));
        if ([...select.options].some(option => option.value === value)) select.value = value;
      });
    } catch (_) { /* The server still validates and snapshots the applicable price on submission. */ }
  }
  customer.addEventListener('change', refreshPrices);
  refreshPrices();
}
