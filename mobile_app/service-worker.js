// Service Worker para PWA
const CACHE_NAME = 'clinica-cel-v3';
const API_BASE = 'https://clinicacel.onrender.com';
const CHECK_INTERVAL = 60000; // Verificar a cada 60 segundos

const urlsToCache = [
  '/mobile_app/',
  '/mobile_app/index.html',
  '/mobile_app/manifest.json',
  '/mobile_app/icon-192.png',
  '/mobile_app/icon-512.png'
];

// Instalar Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
      .then(() => self.skipWaiting())
  );
});

// Ativar Service Worker
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => self.clients.claim())
  );
  
  // Iniciar verificação periódica de notificações
  startNotificationCheck();
});

// Interceptar requisições
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Retornar do cache ou buscar da rede
        return response || fetch(event.request);
      })
  );
});

// Função para verificar notificações pendentes
async function checkPendingNotifications() {
  try {
    // Obter CPF do storage (será definido pelo app quando logar)
    const cpf = await getStoredCpf();
    if (!cpf) {
      return;
    }
    
    const lastCheck = await getStoredLastCheck() || '';
    
    const response = await fetch(`${API_BASE}/api/notifications/pending`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cpf, last_check: lastCheck})
    });
    
    if (!response.ok) {
      return;
    }
    
    const data = await response.json();
    if (data.success && data.notifications && data.notifications.length > 0) {
      // Mostrar cada notificação
      for (const notif of data.notifications) {
        await showNotification(notif);
        // Marcar como enviada
        if (notif.id) {
          try {
            await fetch(`${API_BASE}/api/notifications/mark-sent`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({notification_id: notif.id})
            });
          } catch (e) {
            console.error('Erro ao marcar notificação como enviada:', e);
          }
        }
      }
      
      // Atualizar último check
      await setStoredLastCheck(data.last_check);
    }
  } catch (error) {
    console.error('Erro ao verificar notificações:', error);
  }
}

// Função para mostrar notificação
async function showNotification(notif) {
  const options = {
    body: notif.body,
    icon: '/mobile_app/icon-192.png',
    badge: '/mobile_app/icon-192.png',
    vibrate: [200, 100, 200],
    tag: notif.data?.tag || `repair-${notif.repair_id || 'unknown'}`,
    data: notif.data || {},
    requireInteraction: false,
    silent: false
  };
  
  await self.registration.showNotification(notif.title || 'Clínica CELL', options);
}

// Função para iniciar verificação periódica
function startNotificationCheck() {
  // Verificar imediatamente
  checkPendingNotifications();
  
  // Verificar periodicamente
  setInterval(checkPendingNotifications, CHECK_INTERVAL);
}

// Variável para armazenar CPF (declarada antes das funções)
let storedCpf = null;

// Funções auxiliares para storage
async function getStoredCpf() {
  // Retornar CPF armazenado via mensagem
  return storedCpf;
}

async function getStoredLastCheck() {
  // Usar IndexedDB ou cache para armazenar
  return null;
}

async function setStoredLastCheck(timestamp) {
  // Usar IndexedDB ou cache para armazenar
}

// Listener para mensagens do app (para definir CPF)
self.addEventListener('message', (event) => {
  // Processar mensagens síncronamente quando possível
  if (event.data && event.data.type === 'SET_CPF') {
    // Armazenar CPF para uso nas verificações
    storedCpf = event.data.cpf;
    console.log('CPF definido no service worker:', storedCpf);
    // Verificar imediatamente após definir CPF (assíncrono)
    checkPendingNotifications().catch(err => console.error('Erro ao verificar notificações:', err));
    // Responder se houver porta
    if (event.ports && event.ports[0]) {
      event.ports[0].postMessage({success: true, cpf: storedCpf});
    }
    return;
  }
  
  if (event.data && event.data.type === 'CHECK_NOW') {
    // Verificar notificações imediatamente (assíncrono)
    checkPendingNotifications().catch(err => console.error('Erro ao verificar notificações:', err));
    // Responder se houver porta
    if (event.ports && event.ports[0]) {
      event.ports[0].postMessage({success: true});
    }
    return;
  }
  
  if (event.data && event.data.type === 'GET_CPF') {
    // Responder com CPF armazenado
    if (event.ports && event.ports[0]) {
      event.ports[0].postMessage({cpf: storedCpf});
    }
    return;
  }
  
  // Responder para outras mensagens para evitar erro de canal fechado
  if (event.ports && event.ports[0]) {
    event.ports[0].postMessage({received: true});
  }
});

// Listener para cliques em notificações
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  const data = event.notification.data || {};
  const url = data.url || '/mobile_app/';
  
  event.waitUntil(
    clients.matchAll({type: 'window', includeUncontrolled: true})
      .then((clientList) => {
        // Se já existe uma janela aberta, focar nela
        for (let i = 0; i < clientList.length; i++) {
          const client = clientList[i];
          if (client.url.includes('/mobile_app/') && 'focus' in client) {
            return client.focus().then(() => {
              if (url) {
                return client.navigate(url);
              }
            });
          }
        }
        // Se não existe, abrir nova janela
        if (clients.openWindow && url) {
          return clients.openWindow(url);
        }
      })
  );
});

// CPF será armazenado via mensagem do app
