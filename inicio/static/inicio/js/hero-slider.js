    const HeroSlider = {
        currentIndex: 0,
        totalSlides: 4,
        autoPlayTimer: null,
        autoPlayInterval: 5000,

        init() {
            const slides = document.querySelectorAll('#heroSlidesContainer .hero-slide');
            if (slides.length > 0) {
                this.totalSlides = slides.length;
            }
            const prev = document.getElementById('sliderPrevBtn');
            const next = document.getElementById('sliderNextBtn');
            const wrap = document.getElementById('heroSlider');

            if (prev) prev.addEventListener('click', () => this.prev());
            if (next) next.addEventListener('click', () => this.next());

            if (wrap) {
                wrap.addEventListener('mouseenter', () => this.stopAutoPlay());
                wrap.addEventListener('mouseleave', () => this.startAutoPlay());
            }

            this.goTo(0);
            this.startAutoPlay();
            this.initCountdown();
        },

        goTo(index) {
            this.currentIndex = (index + this.totalSlides) % this.totalSlides;
            const container = document.getElementById('heroSlidesContainer');
            const slides = document.querySelectorAll('#heroSlidesContainer .hero-slide');
            const dots = document.querySelectorAll('#sliderDots .slider-dot');

            if (container) {
                container.style.transform = `translateX(-${this.currentIndex * 100}%)`;
            }

            slides.forEach((slide, i) => {
                if (i === this.currentIndex) {
                    slide.classList.add('active');
                } else {
                    slide.classList.remove('active');
                }
            });

            dots.forEach((dot, i) => {
                if (i === this.currentIndex) {
                    dot.classList.add('active');
                } else {
                    dot.classList.remove('active');
                }
            });
        },

        next() {
            this.goTo(this.currentIndex + 1);
        },

        prev() {
            this.goTo(this.currentIndex - 1);
        },

        startAutoPlay() {
            this.stopAutoPlay();
            this.autoPlayTimer = setInterval(() => {
                this.next();
            }, this.autoPlayInterval);
        },

        stopAutoPlay() {
            if (this.autoPlayTimer) {
                clearInterval(this.autoPlayTimer);
                this.autoPlayTimer = null;
            }
        },

        initCountdown() {
            // Temporizador de 8 horas en bucle para Oferta Flash
            let totalSeconds = 5 * 3600 + 48 * 60 + 20;
            const hEl = document.getElementById('cdHours');
            const mEl = document.getElementById('cdMinutes');
            const sEl = document.getElementById('cdSeconds');

            const fHEl = document.getElementById('flashHours');
            const fMEl = document.getElementById('flashMinutes');
            const fSEl = document.getElementById('flashSeconds');

            setInterval(() => {
                if (totalSeconds <= 0) {
                    totalSeconds = 8 * 3600;
                }
                totalSeconds--;

                const hours = Math.floor(totalSeconds / 3600);
                const minutes = Math.floor((totalSeconds % 3600) / 60);
                const seconds = totalSeconds % 60;

                const hStr = String(hours).padStart(2, '0');
                const mStr = String(minutes).padStart(2, '0');
                const sStr = String(seconds).padStart(2, '0');

                if (hEl) hEl.innerText = hStr;
                if (mEl) mEl.innerText = mStr;
                if (sEl) sEl.innerText = sStr;

                if (fHEl) fHEl.innerText = hStr;
                if (fMEl) fMEl.innerText = mStr;
                if (fSEl) fSEl.innerText = sStr;
            }, 1000);
        }
    };

    // Sub-carrusel / Galería interactiva interna para cada Laptop
    function switchLaptopImg(slideId, imgUrl, thumbBtn) {
        const targetImg = document.getElementById(slideId);
        if (targetImg) {
            targetImg.style.opacity = '0';
            setTimeout(() => {
                targetImg.src = imgUrl;
                targetImg.style.opacity = '1';
            }, 180);
        }
        if (thumbBtn && thumbBtn.parentElement) {
            const thumbs = thumbBtn.parentElement.querySelectorAll('.laptop-mini-thumb');
            thumbs.forEach(t => t.classList.remove('active'));
            thumbBtn.classList.add('active');
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        HeroSlider.init();
    });
