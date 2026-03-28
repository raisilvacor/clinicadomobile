// Language Selection & Translation
window.changeLanguage = function(langCode) {
  // O Google Translate usa um select com a classe goog-te-combo
  const googleCombo = document.querySelector('.goog-te-combo');
  
  if (googleCombo) {
    googleCombo.value = langCode;
    
    // Disparar evento de mudança (necessário para o Google Translate processar)
    if (googleCombo.dispatchEvent) {
      googleCombo.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
    } else if (googleCombo.fireEvent) {
      googleCombo.fireEvent('onchange');
    }

    // Atualizar o visual do botão personalizado
    const langBtn = document.getElementById('langBtn');
    if (langBtn) {
      const img = langBtn.querySelector('img');
      const span = langBtn.querySelector('span');
      if (langCode === 'pt') {
        img.src = "https://flagcdn.com/w20/br.png";
        span.textContent = "PT";
      } else if (langCode === 'es') {
        img.src = "https://flagcdn.com/w20/es.png";
        span.textContent = "ES";
      }
    }
    
    // Esconder o dropdown após selecionar
    const langDropdown = document.getElementById('langDropdown');
    if (langDropdown) {
      langDropdown.classList.remove('active');
    }
  } else {
    console.log('Aguardando carregamento do motor de tradução...');
    // Tentar novamente em breve caso o widget ainda esteja carregando
    setTimeout(() => changeLanguage(langCode), 500);
  }
};

window.googleTranslateElementInit = function() {
  new google.translate.TranslateElement({
    pageLanguage: 'pt',
    includedLanguages: 'pt,es',
    layout: google.translate.TranslateElement.InlineLayout.SIMPLE,
    autoDisplay: false
  }, 'google_translate_element');
  
  // Garantir que o combo do Google seja acessível
  const checkInterval = setInterval(() => {
    const combo = document.querySelector('.goog-te-combo');
    if (combo) {
      console.log('Motor de tradução carregado e pronto.');
      clearInterval(checkInterval);
    }
  }, 1000);
};

(function () {
  const menuToggle = document.querySelector('.menu-toggle');
  const navLinks = document.querySelector('.nav-links');
  const menuOverlay = document.querySelector('.menu-overlay');

  function toggleMenu() {
    if (!menuToggle || !navLinks || !menuOverlay) return;
    menuToggle.classList.toggle('active');
    navLinks.classList.toggle('active');
    menuOverlay.classList.toggle('active');
    document.body.style.overflow = navLinks.classList.contains('active') ? 'hidden' : '';
  }

  if (menuToggle) menuToggle.addEventListener('click', toggleMenu);
  if (menuOverlay) menuOverlay.addEventListener('click', toggleMenu);

  document.querySelectorAll('.nav-links a').forEach((link) => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) toggleMenu();
    });
  });

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
      const href = this.getAttribute('href');
      if (!href || href.length < 2) return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  document.querySelectorAll('.js-email').forEach((el) => {
    const u = el.getAttribute('data-u') || '';
    const d = el.getAttribute('data-d') || '';
    if (!u || !d) return;
    el.setAttribute('href', `mailto:${u}@${d}`);
  });

  document.querySelectorAll('.js-device-img').forEach((img) => {
    img.addEventListener('error', () => {
      const parent = img.parentElement;
      if (!parent) return;
      parent.innerHTML = "<div class='device-image-placeholder'>📱</div>";
    });
  });

  document.querySelectorAll('.js-toggle-next-placeholder').forEach((img) => {
    img.addEventListener('error', () => {
      const next = img.nextElementSibling;
      img.classList.add('is-hidden');
      if (next) next.classList.remove('is-hidden');
    });
  });

  document.querySelectorAll('.brand-img').forEach((img) => {
    img.addEventListener('error', () => {
      const parent = img.parentElement;
      if (!parent) return;
      const name = img.getAttribute('data-name') || img.getAttribute('alt') || '';
      img.remove();
      const div = document.createElement('div');
      div.className = 'brand-fallback';
      div.textContent = name;
      parent.appendChild(div);
    });
  });

  document.querySelectorAll('.lab-image').forEach((img) => {
    img.addEventListener('error', () => {
      const parent = img.parentElement;
      if (!parent) return;
      parent.innerHTML = "<div class='lab-image-placeholder'>🔬</div>";
    });
  });

  const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.style.animation = 'fadeInUp 0.8s ease forwards';
    });
  }, observerOptions);

  document.querySelectorAll('.service-card, .contact-card, .device-card, .lab-image-card, .faq-item').forEach((card) => {
    observer.observe(card);
  });

  // FAQ Accordion
  document.querySelectorAll('.faq-item').forEach((item) => {
    item.addEventListener('click', () => {
      const isActive = item.classList.contains('active');
      
      // Close all other items
      document.querySelectorAll('.faq-item').forEach((otherItem) => {
        otherItem.classList.remove('active');
      });

      // Toggle current item
      if (!isActive) {
        item.classList.add('active');
      }
    });
  });

  // Language Selection & Translation
  const langBtn = document.getElementById('langBtn');
  const langDropdown = document.getElementById('langDropdown');

  if (langBtn && langDropdown) {
    langBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      langDropdown.classList.toggle('active');
    });

    document.addEventListener('click', () => {
      langDropdown.classList.remove('active');
    });
  }

  const video = document.querySelector('.about-video');
  if (video) {
    try {
      video.load();
      const playPromise = video.play();
      if (playPromise && typeof playPromise.catch === 'function') {
        playPromise.catch(() => {
          const playOnInteraction = () => {
            video.play().catch(() => {});
          };
          document.addEventListener('click', playOnInteraction, { once: true });
          document.addEventListener('scroll', playOnInteraction, { once: true });
        });
      }

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
          video.load();
        });
      }

      const videoObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              video.load();
              video.play().catch(() => {});
            }
          });
        },
        { rootMargin: '50px' }
      );
      videoObserver.observe(video);
    } catch (_) {}
  }

  function updateBusinessStatus() {
    fetch('/api/business-status')
      .then((response) => response.json())
      .then((data) => {
        const contactCards = document.querySelectorAll('.contact-card');
        let statusCard = null;
        for (let i = 0; i < contactCards.length; i += 1) {
          const icon = contactCards[i].querySelector('.contact-icon');
          if (icon && icon.textContent.includes('🕒')) {
            statusCard = contactCards[i];
            break;
          }
        }

        if (!statusCard) return;
        const statusIndicator = statusCard.querySelector('.status-indicator');
        const statusText = statusCard.querySelector('.status-text');
        if (!statusIndicator || !statusText) return;

        if (data && data.is_open) {
          statusIndicator.classList.remove('closed');
          statusIndicator.classList.add('open');
          statusText.classList.remove('closed');
          statusText.classList.add('open');
          statusText.textContent = 'ABERTO AGORA';
        } else {
          statusIndicator.classList.remove('open');
          statusIndicator.classList.add('closed');
          statusText.classList.remove('open');
          statusText.classList.add('closed');
          statusText.textContent = 'FECHADO';
        }
      })
      .catch(() => {});
  }

  setInterval(updateBusinessStatus, 60000);
})();
