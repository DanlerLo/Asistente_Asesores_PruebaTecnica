/** Sugiere qué preguntar ante «Sin información suficiente»; la frase canónica del backend no se toca. */
const SUGERENCIAS = [
  '¿Cuál es el plazo máximo del Crédito Agro Crece?',
  '¿Qué cubre Vida Protegida?',
  '¿Cuál es el tiempo objetivo de una PQR?',
];

export function Especialidades({ onSugerencia }: { onSugerencia: (pregunta: string) => void }) {
  return (
    <div className="especialidades" role="note" aria-label="Especialidades del asistente">
      <p>Puedo ayudarte con créditos, microseguros, procedimientos operativos y políticas internas. Prueba con:</p>
      <div className="ejemplos">
        {SUGERENCIAS.map((sugerencia) => (
          <button key={sugerencia} type="button" className="ejemplo" onClick={() => onSugerencia(sugerencia)}>
            {sugerencia}
          </button>
        ))}
      </div>
    </div>
  );
}
