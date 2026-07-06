import { api, getRole } from "../api/client";

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

export function isPushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return null;
  return navigator.serviceWorker.register("/sw.js");
}

export async function subscribeToPush() {
  if (!isPushSupported()) throw new Error("Push notifications aren't supported in this browser.");

  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notification permission was not granted.");

  const registration = await registerServiceWorker();
  const { public_key } = await api.getVapidPublicKey();

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(public_key),
  });

  const raw = subscription.toJSON();
  const payload = { endpoint: raw.endpoint, p256dh: raw.keys.p256dh, auth: raw.keys.auth };

  const role = getRole();
  if (role === "candidate") await api.subscribePushCandidate(payload);
  else await api.subscribePushAdmin(payload);

  return subscription;
}

export async function unsubscribeFromPush() {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;

  await api.unsubscribePush({ endpoint: subscription.endpoint });
  await subscription.unsubscribe();
}
