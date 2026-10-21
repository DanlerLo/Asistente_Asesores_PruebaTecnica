import type { RegistroHistorial } from '../api';
import { EstadoBadge } from './EstadoBadge';

interface Props {
  registros: RegistroHistorial[];
  onSeleccionar: (pregunta: string) => void;
}

export function Historial({ registros, onSeleccionar }: Props) {
  if (registros.length === 0) return null;
  return (
    <section className="historial" aria-label="Historial de consultas">
      <h3>Últimas consultas</h3>
      <ul>
        {registros.map((registro) => (
          <li key={registro.id}>
            <button type="button" onClick={() => onSeleccionar(registro.pregunta)} title="Repetir esta consulta">
              {registro.pregunta}
            </button>
            <EstadoBadge estado={registro.estado} />
          </li>
        ))}
      </ul>
    </section>
  );
}
