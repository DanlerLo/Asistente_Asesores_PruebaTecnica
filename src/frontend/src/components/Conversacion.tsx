import { useEffect, useRef } from 'react';
import type { RespuestaConsulta } from '../api';
import { BurbujaAsistente, hora } from './BurbujaAsistente';

export interface Turno {
  id: number;
  pregunta: string;
  enviada: Date;
  resultado?: RespuestaConsulta; // ausente mientras se procesa
}

const EJEMPLOS = [
  '¿Cuál es el monto máximo del Crédito Productivo Impulso?',
  '¿Qué edad máxima tiene Vida Protegida?',
  '¿Cuál es el tiempo objetivo de un PQR?',
];

interface Props {
  turnos: Turno[];
  onEjemplo: (pregunta: string) => void;
}

/** Conversación tipo chat: asesor a la derecha, asistente a la izquierda (RF-U11). */
export function Conversacion({ turnos, onEjemplo }: Props) {
  const lista = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (lista.current) lista.current.scrollTop = lista.current.scrollHeight;
  }, [turnos]);

  return (
    <div className="mensajes" role="log" aria-label="Conversación" aria-live="polite" ref={lista}>
      {turnos.length === 0 && (
        <div className="bienvenida">
          <p>
            Puedo ayudarte con <strong>productos de crédito</strong>, <strong>microseguros</strong>,{' '}
            <strong>procedimientos operativos</strong> y <strong>políticas internas</strong>, siempre con la
            documentación oficial y citando la fuente.
          </p>
          <div className="ejemplos">
            {EJEMPLOS.map((ejemplo) => (
              <button key={ejemplo} type="button" className="ejemplo" onClick={() => onEjemplo(ejemplo)}>
                {ejemplo}
              </button>
            ))}
          </div>
        </div>
      )}
      {turnos.map((turno) => (
        <div key={turno.id} className="turno">
          <article className="mensaje mensaje-asesor" aria-label="Mensaje del asesor">
            <div className="burbuja">{turno.pregunta}</div>
            <p className="meta">{hora(turno.enviada)}</p>
          </article>
          {turno.resultado ? (
            <BurbujaAsistente resultado={turno.resultado} onSugerencia={onEjemplo} />
          ) : (
            <div className="mensaje mensaje-asistente">
              <p className="burbuja escribiendo" role="status">
                Procesando la consulta…
              </p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
