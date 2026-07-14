export function supportsBrowserNotifications(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function browserNotificationPermission(): NotificationPermission | null {
  if (!supportsBrowserNotifications()) {
    return null;
  }

  return Notification.permission;
}

export async function requestBrowserNotificationPermission(): Promise<NotificationPermission | null> {
  if (!supportsBrowserNotifications()) {
    return null;
  }

  if (Notification.permission !== 'default') {
    return Notification.permission;
  }

  return Notification.requestPermission();
}

export function showBrowserNotification({
  title,
  body,
  tag,
}: {
  title: string;
  body: string;
  tag?: string;
}): boolean {
  if (
    !supportsBrowserNotifications() ||
    Notification.permission !== 'granted'
  ) {
    return false;
  }

  try {
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
