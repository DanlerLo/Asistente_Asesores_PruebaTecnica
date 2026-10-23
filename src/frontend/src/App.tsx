import { useCallback, useEffect, useRef, useState } from 'react';
import {
  cambiarModoLlm,
  consultar,
  ErrorApi,
  esEstadoLlm,
  obtenerEstadoLlm,
  obtenerHistorial,
  obtenerMaxLongitud,
  type EstadoLlm,
  type RegistroHistorial,
} from './api';
import { Compositor } from './components/Compositor';
import { Conversacion, type Turno } from './components/Conversacion';
import { Historial } from './components/Historial';
import { LimiteErrores } from './components/LimiteErrores';
import { SelectorModo } from './components/SelectorModo';

/** Valor de respaldo; el real lo informa el backend en `/api/salud` (RF-U13). */
export const MAX_LONGITUD_PREGUNTA = 1000;
/** Preguntas anteriores que se envían como contexto (el backend usa las 3 más recientes). */
export const MAX_CONTEXTO = 3;

export default function App() {
  const [texto, setTexto] = useState('');
  // Memoria de la conversación: vive en el navegador; el servidor no guarda conversaciones.
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [historial, setHistorial] = useState<RegistroHistorial[]>([]);
  const [estadoLlm, setEstadoLlm] = useState<EstadoLlm | null>(null);
  const [cambiandoModo, setCambiandoModo] = useState(false);
  const [ayudaSinConexion, setAyudaSinConexion] = useState(false);
  const [maxLongitud, setMaxLongitud] = useState(MAX_LONGITUD_PREGUNTA);
  const siguienteId = useRef(1);
  // Cada lectura o cambio del estado del LLM recibe un número; solo se aplica la respuesta más reciente,
  // para que un GET lento no pise el modo que el asesor acaba de cambiar.
  const versionLlm = useRef(0);
  const procesando = turnos.some((turno) => !turno.resultado);

  const cargarHistorial = useCallback(async () => {
    try {
      setHistorial(await obtenerHistorial(10));
    } catch {
      // El historial es informativo: si falla no interrumpe la consulta.
    }
  }, []);

  const cargarEstadoLlm = useCallback(async () => {
    const version = ++versionLlm.current;
    try {
      const estado = await obtenerEstadoLlm();
      if (version === versionLlm.current) setEstadoLlm(esEstadoLlm(estado) ? estado : null);
    } catch {
      if (version === versionLlm.current) setEstadoLlm(null); // Informativo: sin selector, la consulta sigue.
    }
  }, []);

  useEffect(() => {
    void cargarHistorial();
    void cargarEstadoLlm();
    obtenerMaxLongitud()
      .then((valor) => valor && setMaxLongitud(valor))
      .catch(() => {}); // sin /api/salud se usa el valor de respaldo
  }, [cargarHistorial, cargarEstadoLlm]);

  async function cambiarModo(activo: boolean) {
    const version = ++versionLlm.current;
    setCambiandoModo(true);
    try {
      const estado = await cambiarModoLlm(activo);
      if (version === versionLlm.current) setEstadoLlm(estado);
      setAyudaSinConexion(!activo);
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'No se pudo cambiar el modo del asistente.');
      void cargarEstadoLlm(); // muestra el modo real del servidor tras el fallo
    } finally {
      setCambiandoModo(false);
    }
  }

  /** `desdeHistorial`: la pregunta viene del historial; el borrador de la caja de texto no se toca. */
  async function enviar(pregunta: string = texto, desdeHistorial = false) {
    if (procesando) return;
    const limpia = pregunta.trim();
    if (!limpia) {
      setError('Escribe una pregunta antes de consultar.');
      return;
    }
    if (limpia.length > maxLongitud) {
      setError(`La pregunta supera el máximo de ${maxLongitud} caracteres.`);
      return;
    }
    // Contexto: las preguntas ya respondidas de la conversación visible (especificación 006).
    const contexto = turnos.filter((t) => t.resultado).map((t) => t.pregunta).slice(-MAX_CONTEXTO);
    const id = siguienteId.current++;
    setTurnos((previos) => [...previos, { id, pregunta: limpia, enviada: new Date() }]);
    if (!desdeHistorial) setTexto('');
    setError(null);
    try {
      const resultado = await consultar(limpia, contexto);
      setTurnos((previos) => previos.map((t) => (t.id === id ? { ...t, resultado } : t)));
      void cargarHistorial();
    } catch (e) {
      // La pregunta fallida sale de la conversación y vuelve a la caja de texto para corregirla.
      setTurnos((previos) => previos.filter((t) => t.id !== id));
      if (!desdeHistorial) setTexto(pregunta);
      setError(e instanceof ErrorApi ? e.message : 'Ocurrió un error inesperado. Intenta de nuevo.');
    } finally {
      void cargarEstadoLlm(); // la cuota cambia con cada llamada al LLM
    }
  }

  function nuevaConversacion() {
    setTurnos([]);
    setError(null);
  }

  return (
    <main className="app">
      <section className="chat" aria-label="Asistente">
        <header className="chat-cabecera">
          <div className="chat-marca">
            <div className="chat-titulo">
              <h1>Asistente para asesores comerciales</h1>
              <p>Productos de crédito, microseguros, procedimientos y políticas · documentación oficial</p>
            </div>
          </div>
          <div className="chat-acciones">
            {estadoLlm && (
              <SelectorModo
                estado={estadoLlm}
                cambiando={cambiandoModo}
                ayudaSinConexion={ayudaSinConexion}
                onCambiarModo={cambiarModo}
                onCerrarAyuda={() => setAyudaSinConexion(false)}
              />
            )}
            {turnos.length > 0 && (
              <button type="button" className="nueva-conversacion" onClick={nuevaConversacion} disabled={procesando}>
                <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16">
                  <path
                    d="M12 5a7 7 0 1 1-6.6 4.7l1.9.6A5 5 0 1 0 12 7v3L7.5 6 12 2z"
                    fill="currentColor"
                  />
                </svg>
                Nueva conversación
              </button>
            )}
          </div>
        </header>

        <LimiteErrores reiniciar={turnos.length}>
          <Conversacion turnos={turnos} onEjemplo={setTexto} />
        </LimiteErrores>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}

        <Compositor
          texto={texto}
          procesando={procesando}
          maximo={maxLongitud}
          onCambiar={setTexto}
          onEnviar={() => void enviar()}
        />
      </section>

      <Historial
        registros={historial}
        deshabilitado={procesando}
        onSeleccionar={(pregunta) => void enviar(pregunta, true)}
      />
    </main>
  );
}
