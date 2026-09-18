        function renderFullCartPage() {
            const items = CartManager.getItems();
            const container = document.getElementById('cartFullList');
            const pageSubtotal = document.getElementById('pageSubtotal');
            const pageShippingCost = document.getElementById('pageShippingCost');
            const pageTotal = document.getElementById('pageTotal');
            const notice = document.getElementById('pageShippingNotice');
            const noticeText = document.getElementById('pageShippingNoticeText');

            if (!container) return;

            if (items.length === 0) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 50px 20px;">
                        <div style="width:76px; height:76px; background:#f1f5f9; border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 16px auto; font-size:32px; color:#94a3b8;">
                            <i class="fa-solid fa-cart-shopping"></i>
                        </div>
                        <h3 style="font-size: 18px; margin-bottom: 8px; color: #0b1120; font-weight:800;">No tienes productos en tu carrito</h3>
                        <a href="/" style="display: inline-block; padding: 11px 24px; background: #1e40af; color: white; border-radius: 10px; text-decoration: none; font-weight: 800; box-shadow:0 4px 12px rgba(30,64,175,0.3);">
                            Ir al Catálogo
                        </a>
                    </div>
                `;
                if (pageSubtotal) pageSubtotal.innerText = 'S/. 0.00';
                if (pageShippingCost) pageShippingCost.innerText = 'S/. 0.00';
                if (pageTotal) pageTotal.innerText = 'S/. 0.00';
                if (notice) notice.style.display = 'none';
                return;
            }

            let subtotal = 0;
            let html = '';

            items.forEach(item => {
                const sub = item.price * item.qty;
                subtotal += sub;
                html += `
                    <div class="cart-table-row">
                        <div class="row-left">
                            <div class="product-thumb">
                                <i class="${item.icon}"></i>
                            </div>
                            <div>
                                <div class="row-title">${item.name}</div>
                                <div class="row-price-unit">S/. ${item.price.toFixed(2)} c/u</div>
                            </div>
                        </div>
                        <div class="row-right">
                            <div class="cart-item-controls">
                                <button type="button" class="qty-btn" onclick="CartManager.updateQty('${item.id}', -1); renderFullCartPage();">
                                    <i class="fa-solid fa-minus"></i>
                                </button>
                                <span class="qty-display">${item.qty}</span>
                                <button type="button" class="qty-btn" onclick="CartManager.updateQty('${item.id}', 1); renderFullCartPage();">
                                    <i class="fa-solid fa-plus"></i>
                                </button>
                            </div>
                            <div style="font-weight: 900; color: #dc2626; min-width: 80px; text-align: right; font-size:15px;">
                                S/. ${sub.toFixed(2)}
                            </div>
                            <button type="button" class="item-delete-btn" onclick="CartManager.removeItem('${item.id}'); renderFullCartPage();">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;

            const isFree = subtotal >= CartManager.freeShippingThreshold;
            const shipping = isFree ? 0 : CartManager.standardShippingFee;
            const total = subtotal + shipping;

            if (pageSubtotal) pageSubtotal.innerText = `S/. ${subtotal.toFixed(2)}`;
            if (pageShippingCost) {
                if (isFree) {
                    pageShippingCost.innerHTML = `<span style="color:#059669; font-weight:800;"><i class="fa-solid fa-circle-check"></i> Gratis</span>`;
                } else {
                    pageShippingCost.innerHTML = `<span>S/. ${shipping.toFixed(2)}</span>`;
                }
            }
            if (pageTotal) pageTotal.innerText = `S/. ${total.toFixed(2)}`;

            if (notice && noticeText) {
                notice.style.display = 'flex';
                if (isFree) {
                    notice.className = 'shipping-notice-box celebrate-unlocked';
                    noticeText.innerHTML = `🎉 ¡Felicidades! Tu compra superó los S/. ${CartManager.freeShippingThreshold.toFixed(2)} y tienes <strong>Envío Gratis en Caraz</strong>.`;
                } else {
                    notice.className = 'shipping-notice-box warning';
                    const diff = (CartManager.freeShippingThreshold - subtotal).toFixed(2);
                    noticeText.innerHTML = `Costo de envío a domicilio: <strong>S/. ${shipping.toFixed(2)}</strong>. (Agrega <strong>S/. ${diff}</strong> más para delivery gratis).`;
                }
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            renderFullCartPage();
        });
