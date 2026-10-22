import type { CuotaLlm, EstadoLlm } from '../api';

interface Props {
  estado: EstadoLlm;
  cambiando: boolean;
  ayudaSinConexion: boolean;
  onCambiarModo: (activo: boolean) => void;
  onCerrarAyuda: () => void;
}

const NOMBRES: Record<string, string> = { groq: 'Groq' };
const UMBRAL_AVISO = 0.1;

function formatearEspera(segundos: number): string {
  if (segundos < 60) return `${Math.ceil(segundos)} s`;
  const minutos = Math.ceil(segundos / 60);
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.floor(minutos / 60);
  return minutos % 60 ? `${horas} h ${minutos % 60} min` : `${horas} h`;
}

function Cuota({ cuota }: { cuota: CuotaLlm | null }) {
  if (!cuota) return <p className="cuota">Llamadas restantes: se conocerá después de la primera consulta.</p>;
  const { solicitudes_restantes: restantes, solicitudes_limite: limite, solicitudes_reinicio_s: reinicio } = cuota;
  if (restantes === null || limite === null) {
    return <p className="cuota">El proveedor no informó la cuota en su última respuesta.</p>;
  }
  return (
    <>
      <p className="cuota">
        <span>{`Quedan ${restantes} de ${limite} llamadas hoy`}</span>
        {reinicio !== null && <span>{` · recarga en ~${formatearEspera(reinicio)}`}</span>}
      </p>
      {restantes === 0 ? (
        <p className="aviso-cuota" role="alert">
          Cuota agotada: las respuestas salen en modo sin conexión hasta que se recargue.
        </p>
      ) : (
        restantes / limite < UMBRAL_AVISO && (
          <p className="aviso-cuota">Quedan pocas llamadas: considera pasar a modo sin conexión.</p>
        )
      )}
    </>
  );
}

/** Selector «Modo conexión (Groq)» / «Modo sin conexión» con cuota y ayuda (especificación 005, RF-L6). */
export function SelectorModo({ estado, cambiando, ayudaSinConexion, onCambiarModo, onCerrarAyuda }: Props) {
  if (!estado.proveedor) {
    return (
      <div className="modo" role="group" aria-label="Modo del asistente">
        <span className="chip-modo">Modo sin conexión</span>
      </div>
    );
  }
  const conexion = `Modo conexión (${NOMBRES[estado.proveedor] ?? estado.proveedor})`;
  return (
    <div className="modo" role="group" aria-label="Modo del asistente">
      <div className="selector-modo">
        <button
          type="button"
          aria-pressed={estado.activo}
          disabled={cambiando}
          onClick={() => !estado.activo && onCambiarModo(true)}
        >
          {conexion}
        </button>
        <button
          type="button"
          aria-pressed={!estado.activo}
          disabled={cambiando}
          onClick={() => estado.activo && onCambiarModo(false)}
        >
          Modo sin conexión
        </button>
      </div>
      {estado.activo && <Cuota cuota={estado.cuota} />}
      {ayudaSinConexion && (
        <div className="popup-modo" role="dialog" aria-label="Modo sin conexión">
          <p>
            <strong>Modo sin conexión.</strong> Las respuestas salen solo con la documentación oficial, sin enviar datos
            a {NOMBRES[estado.proveedor] ?? estado.proveedor} ni gastar llamadas de la API gratuita. Es inmediato y
            predecible, pero entiende menos las preguntas redactadas de otra forma.
          </p>
          <button type="button" onClick={onCerrarAyuda} autoFocus>
            Entendido
          </button>
        </div>
      )}
    </div>
  );
}
