import { ChatCircleIcon } from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { AppBarButton } from '@vibe/ui/components/AppBarButton';
import { useSupervisor } from '@/shared/hooks/useSupervisor';

export function SupervisorLauncher() {
  const supervisor = useSupervisor();
  const { t } = useTranslation('common');
  if (!supervisor?.enabled) return null;
  return (
    <AppBarButton
      icon={ChatCircleIcon}
      label={t('supervisor.title')}
      isActive={supervisor.open}
      expanded={supervisor.open}
      controls="supervisor-dialog"
      onClick={supervisor.show}
    />
  );
}
