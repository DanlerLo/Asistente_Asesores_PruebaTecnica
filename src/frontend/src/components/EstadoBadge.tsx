import type { Estado } from '../api';

const CLASES: Record<Estado, string> = {
  Exitosa: 'estado estado-exitosa',
  'Sin información suficiente': 'estado estado-sin-info',
  'Bloqueada por seguridad': 'estado estado-bloqueada',
};

export function EstadoBadge({ estado }: { estado: Estado }) {
  return <span className={CLASES[estado] ?? 'estado'}>{estado}</span>;
}
