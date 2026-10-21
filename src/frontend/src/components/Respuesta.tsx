import type { RespuestaConsulta } from '../api';
import { EstadoBadge } from './EstadoBadge';
import { Fuentes } from './Fuentes';

export function Respuesta({ resultado }: { resultado: RespuestaConsulta }) {
  return (
    <section className="respuesta" aria-label="Respuesta">
      <div className="respuesta-cabecera">
        <h2>Respuesta</h2>
        <EstadoBadge estado={resultado.estado} />
      </div>
      <pre className="respuesta-texto">{resultado.respuesta}</pre>
      <Fuentes fuentes={resultado.fuentes} />
      <p className="meta">
        Consulta #{resultado.id} · {new Date(resultado.fecha_hora).toLocaleString('es-CO')} · {resultado.latencia_ms} ms ·
        modo {resultado.modo}
      </p>
    </section>
  );
}
