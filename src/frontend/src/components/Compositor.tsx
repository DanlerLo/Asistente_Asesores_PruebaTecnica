import type { FormEvent, KeyboardEvent } from 'react';

interface Props {
  texto: string;
  procesando: boolean;
  maximo: number;
  onCambiar: (texto: string) => void;
  onEnviar: () => void;
}

/** Caja de texto del chat: Enter envía, Shift+Enter agrega un salto de línea (RF-U1, RF-U11). */
export function Compositor({ texto, procesando, maximo, onCambiar, onEnviar }: Props) {
  function enviar(evento: FormEvent) {
    evento.preventDefault();
    onEnviar();
  }

  function teclas(evento: KeyboardEvent<HTMLTextAreaElement>) {
    if (evento.key === 'Enter' && !evento.shiftKey && !evento.nativeEvent.isComposing) {
      evento.preventDefault();
      if (!procesando) onEnviar();
    }
  }

  return (
    <form className="compositor" onSubmit={enviar}>
      <label htmlFor="pregunta" className="solo-lectores">
        Pregunta
      </label>
      <textarea
        id="pregunta"
        value={texto}
        onChange={(e) => onCambiar(e.target.value)}
        onKeyDown={teclas}
        placeholder="Escribe tu pregunta… (Enter para enviar, Shift+Enter para otra línea)"
        rows={2}
        disabled={procesando}
      />
      <div className="compositor-pie">
        <span className={texto.length > maximo ? 'contador excedido' : 'contador'}>
          {texto.length} / {maximo}
        </span>
        <button type="submit" disabled={procesando}>
          <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16">
            <path d="M3 20.5 21 12 3 3.5l2.4 7.1L14 12l-8.6 1.4z" fill="currentColor" />
          </svg>
          {procesando ? 'Consultando…' : 'Consultar'}
        </button>
      </div>
    </form>
  );
}
