/**
 * Full Piloto System - Gestor de Filtros Dinámicos con Fetch
 * Características:
 *  - Panel lateral deslizante (Offcanvas Drawer) con apertura suave al dar clic
 *  - Botón flotante al costado de la pantalla (Side Tab) y botón en barra de catálogo
 *  - Menús de categorías y partes de PC 100% responsives (Bottom Sheet en móvil y popover en desktop)
 *  - Filtros por: Marcas, Rango de Precios, Specs (Procesadores, RAM, SSD), Categorías, Stock, Ofertas, Orden
 *  - Peticiones asíncronas con Fetch (sin recargar la página)
 *  - Sincronización completa con URL (pushState y popstate)
 */

const CatalogFilterManager = (() => {
    // Estado reactivo de los filtros
    const state = {
        q: '',
        categoria: '',
        precio_min: '',
        precio_max: '',
        marca: '',
        procesador: '',
        ram: '',
        almacenamiento: '',
        orden: 'recientes',
        en_stock: '',
        solo_ofertas: '',
        page: 1
    };

    let searchDebounceTimer = null;
    let abortController = null;

    /**
     * Inicializar estado a partir de la URL actual y vincular eventos
     */
    function init() {
        const params = new URLSearchParams(window.location.search);
        state.q = (params.get('q') || params.get('nombre') || '').trim();
        state.categoria = (params.get('categoria') || '').trim();
        state.precio_min = (params.get('precio_min') || '').trim();
        state.precio_max = (params.get('precio_max') || '').trim();
        state.marca = (params.get('marca') || '').trim();
        state.procesador = (params.get('procesador') || '').trim();
        state.ram = (params.get('ram') || '').trim();
        state.almacenamiento = (params.get('almacenamiento') || '').trim();
        state.orden = (params.get('orden') || 'recientes').trim();
        state.en_stock = (params.get('en_stock') || '').trim();
        state.solo_ofertas = (params.get('solo_ofertas') || '').trim();
        state.page = parseInt(params.get('page'), 10) || 1;

        syncControls();

        // Vincular input de búsqueda principal del header
        const headerInput = document.getElementById('headerSearchInput');
        if (headerInput) {
            headerInput.addEventListener('input', (e) => {
                const clearBtn = document.getElementById('headerSearchClearBtn');
                if (clearBtn) clearBtn.style.display = e.target.value.trim() ? 'block' : 'none';
            });
        }
        const headerClear = document.getElementById('headerSearchClearBtn');
        if (headerClear) {
            headerClear.addEventListener('click', () => {
                clearSearch();
            });
        }

        // Permitir que las entradas de precio apliquen con Enter
        const minInput = document.getElementById('inputPrecioMin');
        const maxInput = document.getElementById('inputPrecioMax');
        [minInput, maxInput].forEach(inp => {
            if (inp) {
                inp.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        applyCustomPrice();
                    }
                });
            }
        });

        // Interceptar clics en las burbujas de categorías superiores para usar fetch
        const bubbleLinks = document.querySelectorAll('.category-bubbles-list a.category-bubble-card');
        bubbleLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                const href = link.getAttribute('href');
                if (!href || href.startsWith('http') || href.includes('wa.me') || href.includes('promosCatalog') || href.includes('catalogLateralDrawer')) return;

                e.preventDefault();
                let catSlug = '';
                try {
                    const url = new URL(href, window.location.origin);
                    catSlug = url.searchParams.get('categoria') || '';
                } catch(err) {
                    catSlug = '';
                }
                onCategoryChange(catSlug, true);
            });
        });

        // Manejar botones Atrás / Adelante del navegador
        window.addEventListener('popstate', () => {
            const params = new URLSearchParams(window.location.search);
            state.q = params.get('q') || '';
            state.categoria = params.get('categoria') || '';
            state.precio_min = params.get('precio_min') || '';
            state.precio_max = params.get('precio_max') || '';
            state.marca = params.get('marca') || '';
            state.procesador = params.get('procesador') || '';
            state.ram = params.get('ram') || '';
            state.almacenamiento = params.get('almacenamiento') || '';
            state.orden = params.get('orden') || 'recientes';
            state.en_stock = params.get('en_stock') || '';
            state.solo_ofertas = params.get('solo_ofertas') || '';
            state.page = parseInt(params.get('page'), 10) || 1;

            syncControls();
            fetchProducts({ isPopState: true });
        });

        // Cerrar con Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeFilterDrawer();
                if (typeof MobileCategoryManager !== 'undefined') {
                    MobileCategoryManager.close();
                }
            }
        });
    }

    /**
     * Configura el comportamiento de un input de búsqueda con debounce
     */
    function setupSearchInput(inputId, clearBtnId) {
        const input = document.getElementById(inputId);
        const clearBtn = document.getElementById(clearBtnId);

        if (!input) return;

        input.addEventListener('input', (e) => {
            const val = e.target.value.trim();
            if (clearBtn) clearBtn.style.display = val ? 'block' : 'none';

            // Sincronizar el otro input si existe
            const otherId = inputId === 'filterInputSearch' ? 'drawerInputSearch' : 'filterInputSearch';
            const otherInput = document.getElementById(otherId);
            if (otherInput && otherInput.value !== e.target.value) {
                otherInput.value = e.target.value;
            }

            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                state.q = val;
                fetchProducts({ resetPage: true });
            }, 360);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(searchDebounceTimer);
                state.q = input.value.trim();
                fetchProducts({ resetPage: true });
            }
        });
    }

    /**
     * Sincronizar controles del DOM con el estado interno
     */
    function syncControls() {
        // Sincronizar input de búsqueda del header
        const headerInput = document.getElementById('headerSearchInput');
        if (headerInput && headerInput.value !== state.q) headerInput.value = state.q;
        const headerClear = document.getElementById('headerSearchClearBtn');
        if (headerClear) headerClear.style.display = state.q ? 'block' : 'none';

        // Selector de Categoría
        const catSelect = document.getElementById('filterSelectCategoria');
        if (catSelect) catSelect.value = state.categoria;

        // Selector de Orden
        const orderSelect = document.getElementById('filterSelectOrden');
        if (orderSelect) orderSelect.value = state.orden || 'recientes';

        // Switches de stock y ofertas
        const stockChecked = ['1', 'true', 'on', 'si'].includes(state.en_stock);
        ['filterCheckStock', 'drawerCheckStock'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.checked = stockChecked;
                if (el.parentElement) el.parentElement.classList.toggle('active', stockChecked);
            }
        });

        const ofertasChecked = ['1', 'true', 'on', 'si'].includes(state.solo_ofertas);
        ['filterCheckOfertas', 'drawerCheckOfertas'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.checked = ofertasChecked;
                if (el.parentElement) el.parentElement.classList.toggle('active', ofertasChecked);
            }
        });

        // Inputs manuales de precio
        const minInp = document.getElementById('inputPrecioMin');
        if (minInp) minInp.value = state.precio_min;
        const maxInp = document.getElementById('inputPrecioMax');
        if (maxInp) maxInp.value = state.precio_max;

        // Chips de marcas activas
        document.querySelectorAll('.brands-chips-container .brand-chip').forEach(btn => {
            const m = btn.getAttribute('data-brand') || btn.textContent.trim();
            if ((!state.marca && m.toLowerCase() === 'todas') || (state.marca && m.toLowerCase() === state.marca.toLowerCase())) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Chips de procesadores
        document.querySelectorAll('.cpu-chips-container .cpu-chip').forEach(btn => {
            const cpu = btn.getAttribute('data-cpu') || '';
            if ((!state.procesador && cpu === '') || (state.procesador && cpu.toLowerCase() === state.procesador.toLowerCase())) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Chips de RAM
        document.querySelectorAll('.ram-chips-container .ram-chip').forEach(btn => {
            const r = btn.getAttribute('data-ram') || '';
            if ((!state.ram && r === '') || (state.ram && r.toLowerCase() === state.ram.toLowerCase())) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Chips de Almacenamiento
        document.querySelectorAll('.storage-chips-container .storage-chip').forEach(btn => {
            const s = btn.getAttribute('data-storage') || '';
            if ((!state.almacenamiento && s === '') || (state.almacenamiento && s.toLowerCase() === state.almacenamiento.toLowerCase())) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Burbujas de categorías
        document.querySelectorAll('.category-bubbles-list a.category-bubble-card').forEach(b => {
            const href = b.getAttribute('href') || '';
            if (href.includes('promosCatalog') || href.includes('catalogLateralDrawer')) return;
            if (!state.categoria && (href === '/' || href.endsWith('/inicio') || !href.includes('categoria='))) {
                b.classList.add('active');
            } else if (state.categoria && href.includes(`categoria=${state.categoria}`)) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });
    }

    /**
     * Construye la QueryString a partir del estado actual
     */
    function buildQueryString() {
        const params = new URLSearchParams();
        if (state.q) params.set('q', state.q);
        if (state.categoria && state.categoria !== 'todas') params.set('categoria', state.categoria);
        if (state.precio_min) params.set('precio_min', state.precio_min);
        if (state.precio_max) params.set('precio_max', state.precio_max);
        if (state.marca && state.marca !== 'todas') params.set('marca', state.marca);
        if (state.procesador && state.procesador !== 'todos') params.set('procesador', state.procesador);
        if (state.ram && state.ram !== 'todas') params.set('ram', state.ram);
        if (state.almacenamiento && state.almacenamiento !== 'todos') params.set('almacenamiento', state.almacenamiento);
        if (state.orden && state.orden !== 'recientes') params.set('orden', state.orden);
        if (state.en_stock) params.set('en_stock', state.en_stock);
        if (state.solo_ofertas) params.set('solo_ofertas', state.solo_ofertas);
        if (state.page && state.page > 1) params.set('page', state.page);
        return params.toString();
    }

    /**
     * Realizar la petición Fetch al backend
     */
    async function fetchProducts(options = {}) {
        if (options.resetPage) {
            state.page = 1;
        }

        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();

        const qs = buildQueryString();
        const requestUrl = window.location.pathname + (qs ? `?${qs}&ajax=1` : '?ajax=1');
        const browserUrl = window.location.pathname + (qs ? `?${qs}` : '');

        showLoader(true);

        try {
            const res = await fetch(requestUrl, {
                signal: abortController.signal,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });

            if (!res.ok) throw new Error(`HTTP error ${res.status}`);

            const data = await res.json();
            if (data.status === 'success') {
                const container = document.getElementById('catalogPartialContainer');
                if (container) {
                    container.innerHTML = data.html;
                }

                updateBadges(data.filtros_activos_count, data.total_productos);
                syncControls();

                // Actualizar URL sin recargar
                if (!options.isPopState) {
                    window.history.pushState(state, '', browserUrl);
                }

                // Scroll suave al catálogo si se solicitó
                if (options.scroll) {
                    const catalogEl = document.getElementById('catalogControlsBar') || document.getElementById('promosCatalog');
                    if (catalogEl) {
                        const yOffset = -70;
                        const y = catalogEl.getBoundingClientRect().top + window.pageYOffset + yOffset;
                        window.scrollTo({ top: y, behavior: 'smooth' });
                    }
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('Error al filtrar productos:', err);
            }
        } finally {
            showLoader(false);
        }
    }

    /**
     * Muestra u oculta el estado de carga
     */
    function showLoader(show) {
        const wrap = document.getElementById('catalogProductsWrap');
        const loader = document.getElementById('catalogFetchLoader');
        if (wrap) wrap.classList.toggle('loading', show);
        if (loader) loader.style.display = show ? 'flex' : 'none';
    }

    /**
     * Actualiza los badges de conteo de filtros y resultados
     */
    function updateBadges(filterCount, totalProducts) {
        // Badge en el botón de la barra de catálogo
        const pillBadge = document.getElementById('btnFilterPillBadge');
        if (pillBadge) {
            pillBadge.textContent = filterCount;
            pillBadge.style.display = filterCount > 0 ? 'inline-flex' : 'none';
        }

        // Badge en el botón lateral flotante
        const sideBadge = document.getElementById('sideTabFiltersBadge');
        if (sideBadge) {
            sideBadge.textContent = filterCount;
            sideBadge.style.display = filterCount > 0 ? 'inline-flex' : 'none';
        }

        // Contador dentro del botón del drawer
        const submitCount = document.getElementById('drawerSubmitCount');
        if (submitCount && typeof totalProducts !== 'undefined') {
            submitCount.textContent = `(${totalProducts})`;
        }

        // Sincronizar visibilidad de vitrinas temáticas (se ocultan si el usuario está buscando o filtrando)
        const showcasesEl = document.getElementById('homeShowcasesContainer');
        if (showcasesEl) {
            const hasFilters = (filterCount > 0) || Boolean(state.q) || Boolean(state.categoria && state.categoria !== 'todas');
            showcasesEl.style.display = hasFilters ? 'none' : 'block';
        }
    }

    /* ========================================================================== */
    /* ACCIONES DEL DRAWER LATERAL                                               */
    /* ========================================================================== */

    function openFilterDrawer() {
        const drawer = document.getElementById('catalogLateralDrawer');
        const backdrop = document.getElementById('catalogLateralBackdrop');
        if (drawer) drawer.classList.add('open');
        if (backdrop) backdrop.classList.add('open');
        document.body.classList.add('filter-drawer-open');
    }

    function closeFilterDrawer() {
        const drawer = document.getElementById('catalogLateralDrawer');
        const backdrop = document.getElementById('catalogLateralBackdrop');
        if (drawer) drawer.classList.remove('open');
        if (backdrop) backdrop.classList.remove('open');
        document.body.classList.remove('filter-drawer-open');
    }

    function toggleFilterDrawer() {
        const drawer = document.getElementById('catalogLateralDrawer');
        if (drawer && drawer.classList.contains('open')) {
            closeFilterDrawer();
        } else {
            openFilterDrawer();
        }
    }

    /* ========================================================================== */
    /* ACCIONES DE FILTRO                                                        */
    /* ========================================================================== */

    function onCategoryChange(catSlug, doScroll = false) {
        state.categoria = catSlug || '';
        fetchProducts({ resetPage: true, scroll: doScroll });
    }

    function onOrderChange(orderValue) {
        state.orden = orderValue || 'recientes';
        fetchProducts({ resetPage: true });
    }

    function onStockChange(checked) {
        state.en_stock = checked ? '1' : '';
        fetchProducts({ resetPage: true });
    }

    function onOfertasChange(checked) {
        state.solo_ofertas = checked ? '1' : '';
        fetchProducts({ resetPage: true });
    }

    function clearSearch() {
        state.q = '';
        const headerInput = document.getElementById('headerSearchInput');
        if (headerInput) headerInput.value = '';
        const headerClear = document.getElementById('headerSearchClearBtn');
        if (headerClear) headerClear.style.display = 'none';
        fetchProducts({ resetPage: true });
    }

    function searchByQuery(queryStr) {
        state.q = queryStr ? String(queryStr).trim() : '';
        state.page = 1;
        syncControls();
        fetchProducts({ resetPage: true, scroll: true });
    }

    function setPriceRange(min, max) {
        state.precio_min = min ? String(min) : '';
        state.precio_max = max ? String(max) : '';
        const minInp = document.getElementById('inputPrecioMin');
        if (minInp) minInp.value = state.precio_min;
        const maxInp = document.getElementById('inputPrecioMax');
        if (maxInp) maxInp.value = state.precio_max;
        fetchProducts({ resetPage: true });
    }

    function applyCustomPrice() {
        const minInp = document.getElementById('inputPrecioMin');
        const maxInp = document.getElementById('inputPrecioMax');
        state.precio_min = minInp ? minInp.value.trim() : '';
        state.precio_max = maxInp ? maxInp.value.trim() : '';
        fetchProducts({ resetPage: true });
    }

    function setMarca(marcaName) {
        state.marca = marcaName || '';
        fetchProducts({ resetPage: true });
    }

    function setProcesador(cpuName) {
        state.procesador = cpuName || '';
        fetchProducts({ resetPage: true });
    }

    function setRam(ramSize) {
        state.ram = ramSize || '';
        fetchProducts({ resetPage: true });
    }

    function setAlmacenamiento(diskSize) {
        state.almacenamiento = diskSize || '';
        fetchProducts({ resetPage: true });
    }

    function setPage(pageNum) {
        state.page = pageNum;
        fetchProducts({ scroll: true });
    }

    function removeFilter(filterType) {
        if (filterType === 'q') {
            clearSearch();
            return;
        } else if (filterType === 'categoria') {
            state.categoria = '';
        } else if (filterType === 'precio') {
            state.precio_min = '';
            state.precio_max = '';
            const minInp = document.getElementById('inputPrecioMin');
            if (minInp) minInp.value = '';
            const maxInp = document.getElementById('inputPrecioMax');
            if (maxInp) maxInp.value = '';
        } else if (filterType === 'marca') {
            state.marca = '';
        } else if (filterType === 'procesador') {
            state.procesador = '';
        } else if (filterType === 'ram') {
            state.ram = '';
        } else if (filterType === 'almacenamiento') {
            state.almacenamiento = '';
        } else if (filterType === 'en_stock') {
            state.en_stock = '';
        } else if (filterType === 'solo_ofertas') {
            state.solo_ofertas = '';
        } else if (filterType === 'orden') {
            state.orden = 'recientes';
        }
        fetchProducts({ resetPage: true });
    }

    function clearAllFilters() {
        state.q = '';
        state.categoria = '';
        state.precio_min = '';
        state.precio_max = '';
        state.marca = '';
        state.procesador = '';
        state.ram = '';
        state.almacenamiento = '';
        state.orden = 'recientes';
        state.en_stock = '';
        state.solo_ofertas = '';
        state.page = 1;

        syncControls();
        fetchProducts({ resetPage: true });
    }

    function scrollToFilters(e) {
        if (e) e.preventDefault();
        openFilterDrawer();
    }

    // Inicializar al cargar el DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        openFilterDrawer,
        closeFilterDrawer,
        toggleFilterDrawer,
        onCategoryChange,
        onOrderChange,
        onStockChange,
        onOfertasChange,
        clearSearch,
        searchByQuery,
        setPriceRange,
        applyCustomPrice,
        setMarca,
        setProcesador,
        setRam,
        setAlmacenamiento,
        setPage,
        removeFilter,
        clearAllFilters,
        scrollToFilters
    };
})();

/**
 * Gestor de Submenús Responsives para Categorías (Partes de PC, Laptops, Gamer, etc.)
 * Permite explorar y seleccionar subcategorías en móvil mediante un Bottom Sheet táctil.
 */
const MobileCategoryManager = (() => {
    function open(catSlug, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        const wrapper = document.querySelector(`.category-bubble-item-wrapper[data-cat="${catSlug}"]`);
        if (!wrapper) return;

        const popover = wrapper.querySelector('.category-subpopover');
        if (!popover) {
            CatalogFilterManager.onCategoryChange(catSlug, true);
            return;
        }

        const titleEl = popover.querySelector('.subpopover-title');
        const allLinkEl = popover.querySelector('.subpopover-all');
        const gridEl = popover.querySelector('.subpopover-grid');

        const sheet = document.getElementById('mobileCatSheet');
        const backdrop = document.getElementById('mobileCatBackdrop');
        const titleTarget = document.getElementById('mobileCatSheetTitle');
        const contentTarget = document.getElementById('mobileCatSheetContent');
        const seeAllTarget = document.getElementById('mobileCatSeeAllBtn');

        if (titleTarget && titleEl) {
            titleTarget.innerHTML = titleEl.innerHTML;
        }

        if (contentTarget && gridEl) {
            contentTarget.innerHTML = gridEl.innerHTML;

            // Interceptar enlaces dentro del contenido para usar Fetch instantáneo
            contentTarget.querySelectorAll('a').forEach(a => {
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    close();

                    const href = a.getAttribute('href') || '';
                    let q = '', cat = '';
                    try {
                        const url = new URL(href, window.location.origin);
                        q = url.searchParams.get('q') || '';
                        cat = url.searchParams.get('categoria') || '';
                    } catch (err) {}

                    if (q) {
                        CatalogFilterManager.searchByQuery(q);
                    } else if (cat) {
                        CatalogFilterManager.onCategoryChange(cat, true);
                    }
                });
            });
        }

        if (seeAllTarget && allLinkEl) {
            seeAllTarget.setAttribute('href', allLinkEl.getAttribute('href') || '#');
            seeAllTarget.onclick = (e) => {
                e.preventDefault();
                close();
                CatalogFilterManager.onCategoryChange(catSlug, true);
            };
        }

        if (sheet) sheet.classList.add('open');
        if (backdrop) backdrop.classList.add('open');
        document.body.classList.add('mobile-cat-sheet-open');
    }

    function close() {
        const sheet = document.getElementById('mobileCatSheet');
        const backdrop = document.getElementById('mobileCatBackdrop');
        if (sheet) sheet.classList.remove('open');
        if (backdrop) backdrop.classList.remove('open');
        document.body.classList.remove('mobile-cat-sheet-open');
    }

    function handleBubbleClick(catSlug, event) {
        // En pantallas táctiles, móviles y tablets (< 1100px), si tiene submenú, abrir el Bottom Sheet
        if (window.innerWidth < 1100) {
            const wrapper = document.querySelector(`.category-bubble-item-wrapper[data-cat="${catSlug}"]`);
            if (wrapper && wrapper.querySelector('.category-subpopover')) {
                open(catSlug, event);
                return;
            }
        }
        // En desktop o categorías sin submenú, aplicar filtro normal
        CatalogFilterManager.onCategoryChange(catSlug, true);
    }

    return {
        open,
        close,
        handleBubbleClick
    };
})();
