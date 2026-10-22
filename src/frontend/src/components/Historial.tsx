import type { RegistroHistorial } from '../api';
import { EstadoBadge } from './EstadoBadge';

interface Props {
  registros: RegistroHistorial[];
  /** Mientras se procesa una consulta no se lanza otra (RF-U12). */
  deshabilitado?: boolean;
  onSeleccionar: (pregunta: string) => void;
}

export function Historial({ registros, deshabilitado = false, onSeleccionar }: Props) {
  if (registros.length === 0) return null;
  return (
    <section className="historial" aria-label="Historial de consultas">
      <h3>Últimas consultas</h3>
      <ul>
        {registros.map((registro) => (
          <li key={registro.id}>
            <button
              type="button"
              onClick={() => onSeleccionar(registro.pregunta)}
              disabled={deshabilitado}
              title="Repetir esta consulta"
            >
              {registro.pregunta}
            </button>
            <EstadoBadge estado={registro.estado} />
          </li>
        ))}
      </ul>
    </section>
  );
}
