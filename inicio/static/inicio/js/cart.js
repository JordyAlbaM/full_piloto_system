const CartManager = {
    storageKey: 'full_piloto_cart_v1',
    whatsappNumber: '51961081784',
    freeShippingThreshold: 100.00,
    standardShippingFee: 5.00,
    provinceShippingFee: 10.00,
    selectedPaymentMethod: 'yape_plin',
    hasCelebratedFreeShipping: false,

    triggerConfetti(targetContainer) {
        if (!targetContainer) return;
        const overlay = document.createElement('div');
        overlay.className = 'confetti-canvas-overlay';
        const colors = ['#059669', '#2563eb', '#38bdf8', '#f59e0b', '#742284', '#00bfa5'];

        for (let i = 0; i < 30; i++) {
            const piece = document.createElement('div');
            piece.className = 'confetti-piece';
            piece.style.left = `${Math.random() * 95}%`;
            piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            piece.style.animationDelay = `${Math.random() * 0.4}s`;
            piece.style.animationDuration = `${1.4 + Math.random() * 1.2}s`;
            overlay.appendChild(piece);
        }

        targetContainer.appendChild(overlay);
        setTimeout(() => {
            overlay.remove();
        }, 2800);
    },

    paymentInfoTemplates: {
        yape_plin: `
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <span style="background:#742284; color:white; font-weight:900; padding:4px 10px; border-radius:8px; font-size:12px; letter-spacing:0.5px;">YAPE</span>
                <span style="background:#00bfa5; color:#0b1120; font-weight:900; padding:4px 10px; border-radius:8px; font-size:12px; letter-spacing:0.5px;">PLIN</span>
                <strong style="color:#0b1120; font-size:14px;">961 081 784</strong>
            </div>
            <p style="color:#475569; font-size:12.5px; margin:0; line-height:1.5;">
                Titular: <strong>Full Piloto System</strong>. Al confirmar tu pedido recibirás la orden y el comprobante directo para validar la transacción al instante.
            </p>
        `,
        tarjeta: `
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <i class="fa-brands fa-cc-visa" style="font-size:26px; color:#1a1f71;"></i>
                <i class="fa-brands fa-cc-mastercard" style="font-size:26px; color:#eb001b;"></i>
                <strong style="color:#0b1120; font-size:13.5px;">POS Móvil / Link Niubiz</strong>
            </div>
            <p style="color:#475569; font-size:12.5px; margin:0; line-height:1.5;">
                Aceptamos todas las tarjetas sin recargo adicional. Llevamos el terminal POS inalámbrico a tu domicilio en Caraz o te facilitamos el enlace seguro de pago.
            </p>
        `,
        efectivo: `
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <i class="fa-solid fa-hand-holding-dollar" style="font-size:22px; color:#059669;"></i>
                <strong style="color:#0b1120; font-size:13.5px;">Pago Contra-entrega en Efectivo</strong>
            </div>
            <p style="color:#475569; font-size:12.5px; margin:0; line-height:1.5;">
                Pagas al repartidor en la puerta de tu domicilio o al recoger en nuestro local de Caraz. Puedes especificar el monto de tu billete para llevarte vuelto exacto.
            </p>
        `,
        transferencia: `
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                <i class="fa-solid fa-building-columns" style="font-size:20px; color:#d97706;"></i>
                <strong style="color:#0b1120; font-size:13.5px;">BCP / BBVA / Banco de la Nación</strong>
            </div>
            <p style="color:#475569; font-size:12.5px; margin:0; line-height:1.5;">
                Cuentas bancarias a nombre de la empresa con confirmación inmediata y entrega de factura o boleta electrónica.
            </p>
        `
    },

    // Catálogo estático de stock disponible por producto
    stockCatalog: {
        '1': 5, 'prod_1': 5,
        '2': 14, 'prod_2': 14,
        '3': 8, 'prod_3': 8,
        '4': 12, 'prod_4': 12,
        '5': 7, 'prod_5': 7,
        '6': 4, 'prod_6': 4,
        '7': 6, 'prod_7': 6,
        '8': 8, 'prod_8': 8,
        '9': 8, 'prod_9': 8,
        '10': 8, 'prod_10': 8,
        '11': 8, 'prod_11': 8,
        '12': 8, 'prod_12': 8,
        '101': 8, 'prod_101': 8,
        '102': 10, 'prod_102': 10,
        '103': 6, 'prod_103': 6,
        '104': 7, 'prod_104': 7
    },

    getMaxStock(productId, fallbackStock = null) {
        if (fallbackStock !== null && fallbackStock !== undefined && !isNaN(fallbackStock) && parseInt(fallbackStock) > 0) {
            return parseInt(fallbackStock);
        }
        if (this.stockCatalog[productId] !== undefined) {
            return this.stockCatalog[productId];
        }
        const cleanId = String(productId).replace('prod_', '');
        if (this.stockCatalog[cleanId] !== undefined) {
            return this.stockCatalog[cleanId];
        }
        return 8; // Stock estático estándar por defecto
    },

    getItems() {
        try {
            return JSON.parse(localStorage.getItem(this.storageKey)) || [];
        } catch(e) {
            return [];
        }
    },

    saveItems(items) {
        localStorage.setItem(this.storageKey, JSON.stringify(items));
        this.updateUI();
    },

    addItem(product, triggerBtn = null) {
        let items = this.getItems();
        
        // Limpieza y parseo ultra robusto de precio
        let rawPrice = product.price;
        if (typeof rawPrice === 'string') {
            rawPrice = rawPrice.replace(/[^\d.,]/g, '').replace(',', '.');
        }
        const parsedPrice = parseFloat(rawPrice) || 0;

        // Limpieza y parseo ultra robusto de stock
        let rawStock = product.maxStock !== undefined ? product.maxStock : product.stock;
        if (typeof rawStock === 'string') {
            rawStock = rawStock.replace(/[^\d]/g, '');
        }
        const maxStock = this.getMaxStock(product.id, rawStock);

        const existingIndex = items.findIndex(item => item.id === product.id);
        const addQty = parseInt(product.qty, 10) || 1;
        let currentItemQty = 1;

        if (existingIndex > -1) {
            const desiredQty = items[existingIndex].qty + addQty;
            if (desiredQty > maxStock) {
                this.showToast({
                    title: `⚠️ Stock máximo alcanzado`,
                    subtitle: `Solo disponemos de ${maxStock} unidades en tienda`,
                    isWarning: true
                });
                return false;
            }
            items[existingIndex].qty = desiredQty;
            items[existingIndex].maxStock = maxStock;
            items[existingIndex].price = parsedPrice || items[existingIndex].price;
            if (product.image || product.imagen_url) {
                items[existingIndex].image = product.image || product.imagen_url;
            }
            currentItemQty = items[existingIndex].qty;
        } else {
            if (addQty > maxStock) {
                this.showToast({
                    title: `⚠️ Stock máximo alcanzado`,
                    subtitle: `Solo disponemos de ${maxStock} unidades en tienda`,
                    isWarning: true
                });
                return false;
            }
            items.push({
                id: product.id,
                name: product.name,
                price: parsedPrice,
                image: product.image || product.imagen_url || '',
                icon: product.icon || 'fa-solid fa-laptop',
                qty: addQty,
                maxStock: maxStock
            });
            currentItemQty = addQty;
        }

        this.saveItems(items);
        this.animateHeaderBadge();

        // Feedback visual en el botón de origen si fue suministrado
        if (triggerBtn) {
            const origHtml = triggerBtn.innerHTML;
            triggerBtn.classList.add('btn-added-success');
            triggerBtn.innerHTML = `<i class="fa-solid fa-check"></i> ¡Agregado! (x${currentItemQty})`;
            setTimeout(() => {
                triggerBtn.classList.remove('btn-added-success');
                triggerBtn.innerHTML = origHtml;
            }, 1400);
        }

        this.showToast({
            title: `¡${product.name} agregado!`,
            qty: currentItemQty,
            maxStock: maxStock,
            totalPrice: parsedPrice * currentItemQty
        });

        // Abrir el drawer del carrito para que el usuario vea inmediatamente su producto añadido
        this.openCart();

        return true;
    },

    animateHeaderBadge() {
        const badges = document.querySelectorAll('.cart-badge');
        const icons = document.querySelectorAll('.cart-trigger-btn i, .action-icon-circle i');
        
        badges.forEach(b => {
            b.classList.remove('pop-anim');
            void b.offsetWidth; // Trigger reflow
            b.classList.add('pop-anim');
        });

        icons.forEach(i => {
            i.classList.remove('cart-icon-bump');
            void i.offsetWidth;
            i.classList.add('cart-icon-bump');
        });
    },

    updateQty(productId, delta) {
        let items = this.getItems();
        const index = items.findIndex(item => item.id === productId);
        if (index > -1) {
            const maxStock = this.getMaxStock(productId, items[index].maxStock);
            const nextQty = items[index].qty + delta;

            if (delta > 0 && nextQty > maxStock) {
                this.showToast({
                    title: `⚠️ Stock máximo de ${maxStock} unidades`,
                    subtitle: `No se pueden agregar más unidades de este producto`,
                    isWarning: true
                });
                return;
            }

            items[index].qty = nextQty;
            items[index].maxStock = maxStock;

            if (items[index].qty <= 0) {
                items.splice(index, 1);
            }
            this.saveItems(items);
        }
    },

    removeItem(productId) {
        let items = this.getItems();
        items = items.filter(item => item.id !== productId);
        this.saveItems(items);
    },

    clearCart() {
        if (confirm('¿Deseas vaciar todos los productos del carrito?')) {
            this.saveItems([]);
        }
    },

    openCart() {
        document.getElementById('cartDrawer').classList.add('open');
        document.getElementById('cartOverlay').classList.add('active');
        document.body.style.overflow = 'hidden';
    },

    closeCart() {
        document.getElementById('cartDrawer').classList.remove('open');
        document.getElementById('cartOverlay').classList.remove('active');
        document.body.style.overflow = '';
    },

    openCheckoutModal() {
        const items = this.getItems();
        if (items.length === 0) {
            alert('Tu carrito está vacío. Agrega productos para pagar.');
            return;
        }
        this.selectPayment('yape_plin');
        this.onDeliveryOptionChanged();
        document.getElementById('checkoutModalOverlay').classList.add('active');
    },

    closeCheckoutModal() {
        document.getElementById('checkoutModalOverlay').classList.remove('active');
    },

    selectPayment(method, cardElement) {
        this.selectedPaymentMethod = method;
        document.querySelectorAll('.payment-choice-card').forEach(c => c.classList.remove('selected'));
        if (cardElement) {
            cardElement.classList.add('selected');
        } else {
            const defaultCard = document.querySelector(`.payment-choice-card[onclick*="${method}"]`);
            if (defaultCard) defaultCard.classList.add('selected');
        }

        const box = document.getElementById('paymentDynamicBox');
        if (box && this.paymentInfoTemplates[method]) {
            box.innerHTML = this.paymentInfoTemplates[method];
        }
    },

    getDeliveryCost(subtotal, deliveryType) {
        if (deliveryType === 'recojo_tienda') return 0;
        if (deliveryType === 'provincia') return this.provinceShippingFee;
        if (subtotal >= this.freeShippingThreshold) {
            return 0;
        } else {
            return this.standardShippingFee;
        }
    },

    onDeliveryOptionChanged() {
        const select = document.getElementById('orderDeliveryType');
        const deliveryType = select ? select.value : 'delivery_caraz';
        const addressGroup = document.getElementById('addressInputGroup');

        if (addressGroup) {
            if (deliveryType === 'recojo_tienda') {
                addressGroup.style.display = 'none';
            } else {
                addressGroup.style.display = 'block';
            }
        }

        const items = this.getItems();
        let subtotal = 0;
        items.forEach(i => subtotal += (i.price * i.qty));

        const shipping = this.getDeliveryCost(subtotal, deliveryType);
        const total = subtotal + shipping;

        const badge = document.getElementById('checkoutDeliveryBadge');
        const amountEl = document.getElementById('checkoutFinalAmount');

        if (badge) {
            if (deliveryType === 'recojo_tienda') {
                badge.innerText = 'Recojo en tienda sin costo (S/. 0.00)';
            } else if (deliveryType === 'provincia') {
                badge.innerText = `Envío provincia (+S/. ${this.provinceShippingFee.toFixed(2)})`;
            } else {
                badge.innerText = shipping === 0 ? '¡Envío Gratis en Caraz aplicado!' : `Costo de envío Caraz: +S/. ${shipping.toFixed(2)}`;
            }
        }

        if (amountEl) {
            amountEl.innerText = `S/. ${total.toFixed(2)}`;
        }
    },

    toastTimer: null,

    showToast(data) {
        const toast = document.getElementById('cartToast');
        const titleEl = document.getElementById('cartToastTitle');
        const subtitleEl = document.getElementById('cartToastSubtitle');
        if (!toast) return;

        if (typeof data === 'string') {
            if (titleEl) titleEl.innerText = data;
            if (subtitleEl) subtitleEl.innerHTML = `Actualizado en el carrito`;
            toast.style.borderLeftColor = '#10b981';
        } else if (typeof data === 'object') {
            if (titleEl) titleEl.innerText = data.title;
            if (data.isWarning) {
                toast.style.borderLeftColor = '#f59e0b';
                if (subtitleEl) {
                    subtitleEl.innerHTML = `<span style="color:#fbbf24; font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> ${data.subtitle || 'Límite de inventario'}</span>`;
                }
            } else {
                toast.style.borderLeftColor = '#10b981';
                if (subtitleEl) {
                    if (data.subtitle) {
                        subtitleEl.innerHTML = data.subtitle;
                    } else if (data.qty > 1) {
                        const stockInfo = data.maxStock ? ` (Máx: ${data.maxStock})` : '';
                        subtitleEl.innerHTML = `<span class="qty-pill"><i class="fa-solid fa-boxes-stacked"></i> x${data.qty} en carrito${stockInfo}</span> Subtotal: <strong>S/. ${data.totalPrice.toFixed(2)}</strong>`;
                    } else {
                        const stockInfo = data.maxStock ? ` (Disponibles: ${data.maxStock})` : '';
                        subtitleEl.innerHTML = `<span class="qty-pill">x1 unidad</span> Agregado con éxito${stockInfo}`;
                    }
                }
            }
        }

        toast.classList.add('show');
        if (this.toastTimer) clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => {
            toast.classList.remove('show');
        }, 2400);
    },

    async submitCheckoutOrder(event) {
        event.preventDefault();
        const items = this.getItems();
        if (items.length === 0) return;

        const submitBtn = event.target.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Registrando pedido...';
        }

        const name = document.getElementById('orderCustomerName').value.trim();
        const phone = document.getElementById('orderCustomerPhone').value.trim();
        const deliverySelect = document.getElementById('orderDeliveryType');
        const deliveryType = deliverySelect ? deliverySelect.value : 'delivery_caraz';
        const deliveryText = deliverySelect ? deliverySelect.options[deliverySelect.selectedIndex].text : 'Delivery Caraz';
        const address = document.getElementById('orderCustomerAddress') ? document.getElementById('orderCustomerAddress').value.trim() : (deliveryType === 'recojo_tienda' ? 'Recojo en tienda física Caraz' : '');
        const notes = document.getElementById('orderNotes') ? document.getElementById('orderNotes').value.trim() : '';

        // Formatear items para backend (asegurar id numérico para productos de base de datos)
        const itemsPayload = items.map(it => {
            const rawId = it.id.toString();
            const numericId = parseInt(rawId.replace(/\D/g, ''), 10) || 1;
            return {
                id: numericId,
                cantidad: it.qty,
                nombre: it.name
            };
        });

        const payMethodMap = {
            'yape_plin': 'yape',
            'tarjeta': 'transferencia',
            'efectivo': 'efectivo',
            'transferencia': 'transferencia'
        };

        const backendPayload = {
            nombre: name,
            telefono: phone,
            dni: '',
            direccion: address || 'Entrega local Caraz',
            referencia: deliveryText,
            metodo_pago: payMethodMap[this.selectedPaymentMethod] || 'yape',
            notas: notes,
            items: itemsPayload
        };

        let pedidoBackendId = null;

        try {
            const response = await fetch('/api/crear-pedido/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(backendPayload)
            });

            const resData = await response.json();

            if (!response.ok || !resData.success) {
                alert('⚠️ No se pudo procesar el pedido: ' + (resData.error || 'Error del servidor'));
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;
                }
                return;
            }

            pedidoBackendId = resData.pedido_id;

        } catch (err) {
            console.error('Error enviando al backend:', err);
            alert('⚠️ Error de conexión con el servidor. Revisa tu conexión a internet.');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }
            return;
        }

        // Armado del mensaje con número de pedido oficial del sistema
        let subtotal = 0;
        let itemsText = '';

        items.forEach((item, index) => {
            const sub = item.price * item.qty;
            subtotal += sub;
            itemsText += `  ${index + 1}. *${item.name}*\n     x${item.qty} un. — S/. ${sub.toFixed(2)} (S/. ${item.price.toFixed(2)} c/u)\n`;
        });

        const shippingCost = this.getDeliveryCost(subtotal, deliveryType);
        const total = subtotal + shippingCost;

        const payNames = {
            yape_plin: '📱 Yape / Plin (961 081 784)',
            tarjeta: '💳 Tarjeta Débito/Crédito (POS / Link)',
            efectivo: '💵 Efectivo Contra-entrega',
            transferencia: '🏦 Transferencia BCP/BBVA'
        };
        const paymentName = payNames[this.selectedPaymentMethod] || this.selectedPaymentMethod;

        let message = `🛒 *PEDIDO OFICIAL #${pedidoBackendId} - FULL PILOTO SYSTEM*\n`;
        message += `==============================\n`;
        message += `👤 *Cliente:* ${name}\n`;
        message += `📱 *Celular:* ${phone}\n`;
        message += `📍 *Modalidad:* ${deliveryText}\n`;
        if (address && deliveryType !== 'recojo_tienda') {
            message += `🏠 *Dirección:* ${address}\n`;
        }
        message += `💳 *Forma de Pago:* ${paymentName}\n`;
        if (notes) {
            message += `📝 *Nota:* ${notes}\n`;
        }
        message += `==============================\n`;
        message += `📦 *PRODUCTOS:* \n`;
        message += itemsText;
        message += `==============================\n`;
        message += `Subtotal: S/. ${subtotal.toFixed(2)}\n`;
        message += `Envío: ${shippingCost === 0 ? '¡GRATIS!' : 'S/. ' + shippingCost.toFixed(2)}\n`;
        message += `💰 *TOTAL REGISTRADO:* *S/. ${total.toFixed(2)}*\n\n`;
        message += `✅ *¡Hola Full Piloto System! Mi pedido #${pedidoBackendId} ya quedó registrado en su sistema web. Aquí les envío mi comprobante/datos para despacharlo.*`;

        // Vaciar carrito ya que la orden fue persistida exitosamente
        this.saveItems([]);

        const encoded = encodeURIComponent(message);
        const whatsappUrl = `https://wa.me/${this.whatsappNumber}?text=${encoded}`;

        window.open(whatsappUrl, '_blank');
        this.closeCheckoutModal();
        this.closeCart();
        this.showToast({
            title: `🎉 ¡Pedido #${pedidoBackendId} registrado!`,
            subtitle: `Se abrió WhatsApp para coordinar tu entrega`,
            isWarning: false
        });

        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    },

    getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') return value;
        }
        return '';
    },


    updateUI() {
        const items = this.getItems();
        const container = document.getElementById('cartItemsList');
        const countBadges = document.querySelectorAll('.cart-badge');
        const headerCount = document.getElementById('cartHeaderCount');
        const subtotalDisplays = document.querySelectorAll('.cart-trigger-btn .main-value, #cartSubtotal');
        const cartTotalDisplay = document.getElementById('cartTotal');
        const shippingProgressFill = document.getElementById('shippingProgressFill');
        const shippingMeterText = document.getElementById('shippingMeterText');
        const shippingMeterStatus = document.getElementById('shippingMeterStatus');
        const shippingDetailHint = document.getElementById('shippingDetailHint');
        const shippingCostLabel = document.getElementById('cartShippingCost');
        const footer = document.getElementById('cartFooter');

        let totalQty = 0;
        let subtotal = 0;

        items.forEach(item => {
            totalQty += item.qty;
            subtotal += (item.price * item.qty);
        });

        // Actualizar badges
        countBadges.forEach(badge => badge.innerText = totalQty);
        if (headerCount) headerCount.innerText = `${totalQty} ${totalQty === 1 ? 'producto' : 'productos'}`;

        // Cálculo de envío para el resumen del drawer
        const isFree = subtotal >= this.freeShippingThreshold && subtotal > 0;
        const shippingFee = (subtotal === 0) ? 0 : (isFree ? 0 : this.standardShippingFee);
        const finalTotal = subtotal + shippingFee;

        // Displays
        subtotalDisplays.forEach(el => el.innerText = `S/. ${subtotal.toFixed(2)}`);
        if (cartTotalDisplay) cartTotalDisplay.innerText = `S/. ${finalTotal.toFixed(2)}`;

        if (shippingCostLabel) {
            if (subtotal === 0) {
                shippingCostLabel.innerText = `S/. 0.00`;
                shippingCostLabel.style.color = '#64748b';
            } else if (isFree) {
                shippingCostLabel.innerHTML = `<span style="color:#059669; font-weight:800;"><i class="fa-solid fa-circle-check"></i> Gratis</span>`;
            } else {
                shippingCostLabel.innerHTML = `<span style="color:#0b1120;">S/. ${this.standardShippingFee.toFixed(2)}</span> <small style="color:#dc2626; font-size:11px; font-weight:700;">(Tarifa fija)</small>`;
            }
        }

        // Barra de Envío Gratis
        const meterContainer = document.querySelector('.cart-shipping-meter');

        if (shippingProgressFill && shippingMeterText && shippingMeterStatus) {
            if (subtotal === 0) {
                this.hasCelebratedFreeShipping = false;
                if (meterContainer) meterContainer.classList.remove('unlocked-celebrate');
                shippingProgressFill.classList.remove('celebrate-fill');
                shippingProgressFill.style.width = `0%`;
                shippingMeterStatus.innerText = `S/. 0 / S/. ${this.freeShippingThreshold}`;
                shippingMeterText.innerHTML = `<i class="fa-solid fa-truck-fast"></i> Delivery Caraz: <strong>S/. ${this.standardShippingFee.toFixed(2)}</strong>`;
            } else if (isFree) {
                shippingProgressFill.style.width = `100%`;
                shippingProgressFill.classList.add('celebrate-fill');
                if (meterContainer) meterContainer.classList.add('unlocked-celebrate');

                shippingMeterStatus.innerHTML = `<span class="free-shipping-celebration-badge"><i class="fa-solid fa-gift"></i> ¡GRATIS!</span>`;
                shippingMeterText.innerHTML = `🎉 <strong>¡Felicidades! Desbloqueaste Envío Gratis</strong> (Ahorras S/. ${this.standardShippingFee.toFixed(2)})`;
            } else {
                this.hasCelebratedFreeShipping = false;
                if (meterContainer) meterContainer.classList.remove('unlocked-celebrate');
                shippingProgressFill.classList.remove('celebrate-fill');

                const percent = Math.min(99, Math.round((subtotal / this.freeShippingThreshold) * 100));
                const diff = (this.freeShippingThreshold - subtotal).toFixed(2);
                shippingProgressFill.style.width = `${percent}%`;
                shippingMeterStatus.innerText = `${percent}%`;
                shippingMeterText.innerHTML = `<i class="fa-solid fa-truck-fast"></i> Agrega <strong>S/. ${diff}</strong> más para <strong>Envío Gratis</strong>`;
            }
        }

        if (shippingDetailHint) {
            if (isFree) {
                shippingDetailHint.innerHTML = `<i class="fa-solid fa-shield-check" style="color:#059669;"></i> ¡Tu pedido califica para despacho en Caraz sin costo de delivery!`;
            } else {
                shippingDetailHint.innerHTML = `<i class="fa-solid fa-circle-info"></i> Compras menores a S/. ${this.freeShippingThreshold.toFixed(2)} tienen tarifa plana de delivery de <strong>S/. ${this.standardShippingFee.toFixed(2)}</strong>.`;
            }
        }

        // Renderizar items
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = `
                <div class="cart-empty-state">
                    <div class="empty-icon"><i class="fa-solid fa-cart-arrow-down"></i></div>
                    <h3>Tu carrito está vacío</h3>
                    <p>Explora nuestras promociones y componentes en Caraz y agrégalos para pagar.</p>
                    <button type="button" class="cart-action-btn" style="background: var(--fps-primary); color:white;" onclick="CartManager.closeCart()">
                        Ver promociones ahora
                    </button>
                </div>
            `;
            if (footer) footer.style.opacity = '0.5';
            return;
        }

        if (footer) footer.style.opacity = '1';

        let html = '';
        items.forEach(item => {
            const itemSubtotal = (item.price * item.qty).toFixed(2);
            const maxStock = this.getMaxStock(item.id, item.maxStock);
            const isMaxReached = item.qty >= maxStock;
            const itemMediaHtml = item.image 
                ? `<img src="${item.image}" alt="${item.name}" class="cart-item-img" onerror="this.outerHTML='<i class=\\'${item.icon || 'fa-solid fa-laptop'}\\'></i>'">`
                : `<i class="${item.icon || 'fa-solid fa-laptop'}"></i>`;

            html += `
                <div class="cart-item" data-id="${item.id}">
                    <div class="cart-item-icon">
                        ${itemMediaHtml}
                    </div>
                    <div class="cart-item-info">
                        <div class="cart-item-title" title="${item.name}">${item.name}</div>
                        <div class="cart-item-unit-price">
                            S/. ${item.price.toFixed(2)} c/u • <span style="color:${isMaxReached ? '#d97706' : '#64748b'}; font-weight:${isMaxReached ? '700' : '500'};">${isMaxReached ? 'Máx. ' + maxStock + ' disponible' : 'Stock: ' + maxStock}</span>
                        </div>
                        <div class="cart-item-controls">
                            <button type="button" class="qty-btn" onclick="CartManager.updateQty('${item.id}', -1)" title="Reducir">
                                <i class="fa-solid fa-minus"></i>
                            </button>
                            <span class="qty-display">${item.qty}</span>
                            <button type="button" class="qty-btn" ${isMaxReached ? 'disabled style="opacity:0.4; cursor:not-allowed;"' : ''} onclick="CartManager.updateQty('${item.id}', 1)" title="${isMaxReached ? 'Stock máximo alcanzado' : 'Aumentar'}">
                                <i class="fa-solid fa-plus"></i>
                            </button>
                        </div>
                    </div>
                    <div class="cart-item-subtotal">
                        <button type="button" class="item-delete-btn" onclick="CartManager.removeItem('${item.id}')" title="Eliminar producto">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                        <span class="item-total-price">S/. ${itemSubtotal}</span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    hideToast() {
        const toast = document.getElementById('cartToast');
        if (toast) {
            toast.classList.remove('show');
        }
        if (this.toastTimer) {
            clearTimeout(this.toastTimer);
            this.toastTimer = null;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    CartManager.updateUI();

    document.querySelectorAll('.cart-trigger-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            CartManager.openCart();
        });
    });

    document.querySelectorAll('.btn-promo-action:not([onclick])').forEach((btn, index) => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const card = this.closest('.promo-card');
            if (card) {
                const name = card.querySelector('.promo-name')?.innerText.trim() || `Promo ${index + 1}`;
                const priceText = card.querySelector('.price-main')?.innerText.replace('S/.', '').trim() || '0';
                const price = parseFloat(priceText) || 0;
                const iconClass = card.querySelector('.promo-icon-large i')?.className || 'fa-solid fa-laptop';

                const added = CartManager.addItem({
                    id: `promo_${index + 1}`,
                    name: name,
                    price: price,
                    icon: iconClass,
                    qty: 1
                });

                if (added) {
                    const currentItem = CartManager.getItems().find(i => i.id === `promo_${index + 1}`);
                    const currentQty = currentItem ? currentItem.qty : 1;

                    const originalHtml = btn.innerHTML;
                    btn.classList.add('btn-added-success');
                    btn.innerHTML = currentQty > 1 ? `<i class="fa-solid fa-check"></i> ¡Agregado! (x${currentQty})` : `<i class="fa-solid fa-check"></i> ¡Agregado!`;
                    setTimeout(() => {
                        btn.classList.remove('btn-added-success');
                        btn.innerHTML = originalHtml;
                    }, 1400);
                }
            }
        });
    });
});
