/* Service worker do TJSP Aprovação.
 * - Guarda em cache apenas o "casco" do app (HTML, JS, CSS, ícones) para abrir mais rápido.
 * - NUNCA guarda respostas de /api: dados de estudo vêm sempre do servidor (fonte única de verdade).
 * - Sem rede, o app abre, mas avisa que precisa do servidor para mostrar e salvar os dados. */
const VERSAO = "tjsp-v1";
const CASCO = ["/", "/favicon.svg", "/icon-192.png", "/icon-512.png", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSAO).then((c) => c.addAll(CASCO)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((chaves) => Promise.all(chaves.filter((k) => k !== VERSAO).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (req.mode === "navigate") {
    // Rede primeiro (pega a versão nova); cache só como reserva offline.
    e.respondWith(fetch(req).catch(() => caches.match("/")));
    return;
  }
  // Arquivos com hash em /assets: cache primeiro.
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) { const copia = res.clone(); caches.open(VERSAO).then((c) => c.put(req, copia)); }
      return res;
    }))
  );
});
