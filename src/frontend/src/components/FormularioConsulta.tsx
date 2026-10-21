import { useState, type FormEvent } from 'react';

interface Props {
  procesando: boolean;
  onEnviar: (pregunta: string) => void;
}

const EJEMPLOS = [
  '¿Cuál es el monto máximo del Crédito Productivo Impulso?',
  '¿Qué edad máxima tiene Vida Protegida?',
  '¿Cuál es el tiempo objetivo de un PQR?',
];

export function FormularioConsulta({ procesando, onEnviar }: Props) {
  const [pregunta, setPregunta] = useState('');

  function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();
    onEnviar(pregunta);
  }

  return (
    <form className="formulario" onSubmit={manejarEnvio}>
      <label htmlFor="pregunta">Pregunta</label>
      <textarea
        id="pregunta"
        value={pregunta}
        onChange={(e) => setPregunta(e.target.value)}
        placeholder="Ejemplo: ¿Cuál es el plazo máximo del Crédito Agro Crece?"
        rows={3}
        disabled={procesando}
      />
      <div className="acciones">
        <button type="submit" disabled={procesando}>
          {procesando ? 'Consultando…' : 'Consultar'}
        </button>
        <span className="contador">{pregunta.length} / 1000</span>
      </div>
      <div className="ejemplos">
        <span>Ejemplos:</span>
        {EJEMPLOS.map((ejemplo) => (
          <button key={ejemplo} type="button" className="ejemplo" onClick={() => setPregunta(ejemplo)} disabled={procesando}>
            {ejemplo}
          </button>
        ))}
      </div>
    </form>
  );
}
