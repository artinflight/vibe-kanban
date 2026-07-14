export function supportsBrowserNotifications(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function supportsServiceWorkerNotifications(): boolean {
  return (
    supportsBrowserNotifications() &&
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator
  );
}

export function browserNotificationPermission(): NotificationPermission | null {
  if (!supportsBrowserNotifications()) {
    return null;
  }

  return Notification.permission;
}

async function notificationServiceWorkerRegistration(): Promise<ServiceWorkerRegistration | null> {
  if (!supportsServiceWorkerNotifications()) {
    return null;
  }

  try {
    return await navigator.serviceWorker.register('/vk-notifications-sw.js');
  } catch (error) {
    console.error('Failed to register notification service worker:', error);
    return null;
  }
}

export async function requestBrowserNotificationPermission(): Promise<NotificationPermission | null> {
  if (!supportsBrowserNotifications()) {
    return null;
  }

  if (Notification.permission !== 'default') {
    return Notification.permission;
  }

  const permission = await Notification.requestPermission();
  if (permission === 'granted') {
    await notificationServiceWorkerRegistration();
  }

  return permission;
}

export async function showBrowserNotification({
  title,
  body,
  tag,
  url = '/',
}: {
  title: string;
  body: string;
  tag?: string;
  url?: string;
}): Promise<boolean> {
  if (
    !supportsBrowserNotifications() ||
    Notification.permission !== 'granted'
  ) {
    return false;
  }

  try {
    const registration = await notificationServiceWorkerRegistration();
    if (registration) {
      await registration.showNotification(title, {
        body,
        tag,
        data: { url },
        icon: '/apple-touch-icon.png',
        badge: '/favicon-vk-light-maskable.svg',
      });
      return true;
    }

    new Notification(title, {
      body,
      tag,
    });
    return true;
  } catch (error) {
    console.error('Failed to show browser notification:', error);
    return false;
  }
}
