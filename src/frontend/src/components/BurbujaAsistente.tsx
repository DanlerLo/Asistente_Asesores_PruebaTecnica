import type { RespuestaConsulta } from '../api';
import { Especialidades } from './Especialidades';
import { EstadoBadge } from './EstadoBadge';
import { Fuentes } from './Fuentes';

export const hora = (fecha: string | Date) =>
  new Date(fecha).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });

/** Respuesta del asistente: texto íntegro, estado, fuentes y metadatos (RF-U4, RF-U5). */
interface Props {
  resultado: RespuestaConsulta;
  onSugerencia: (pregunta: string) => void;
}

export function BurbujaAsistente({ resultado, onSugerencia }: Props) {
  return (
    <article className="mensaje mensaje-asistente" aria-label="Respuesta del asistente">
      <div className="burbuja respuesta">
        <EstadoBadge estado={resultado.estado} />
        <pre className="respuesta-texto">{resultado.respuesta}</pre>
        {resultado.estado === 'Sin información suficiente' && <Especialidades onSugerencia={onSugerencia} />}
        <Fuentes fuentes={resultado.fuentes} />
      </div>
      <p className="meta">
        {hora(resultado.fecha_hora)} · consulta #{resultado.id} · modo {resultado.modo} · {resultado.latencia_ms} ms
      </p>
    </article>
  );
}
